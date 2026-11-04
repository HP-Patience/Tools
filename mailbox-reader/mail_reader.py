"""On-demand Microsoft Graph mail access; never polls or logs credentials."""
import json
import socket
import threading
import time
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import HTTPRedirectHandler, Request, build_opener


class MailError(Exception):
    def __init__(self, message, status=502, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(url, data=None, headers=None):
    request = Request(url, data=data, headers=headers or {})
    try:
        with build_opener(NoRedirect).open(request, timeout=20) as response:
            raw = response.read(8 * 1024 * 1024 + 1)
            if len(raw) > 8 * 1024 * 1024:
                raise MailError('邮件内容过大，请使用原邮箱客户端查看')
            return json.loads(raw)
    except HTTPError as error:
        status = error.code
        retry = error.headers.get('Retry-After', '')
        if status == 429:
            seconds = int(retry) if retry.isdigit() else 60
            raise MailError(f'微软暂时限制请求，请在 {seconds} 秒后手动刷新', 429, seconds) from None
        if status in (400, 401):
            raise MailError('邮箱授权无效或已过期，或导入的 Token 不适用于当前应用。请重新获取该邮箱的授权信息。', 401) from None
        if status == 403:
            raise MailError('此应用没有读取该邮箱的 Graph 权限，需要为同一应用重新授权 Mail.Read。', 403) from None
        if status == 404:
            raise MailError('未找到邮件或此账号不支持当前邮件接口', 404) from None
        raise MailError('微软邮件服务暂时不可用，请稍后手动重试') from None
    except (URLError, TimeoutError, socket.timeout, OSError):
        raise MailError('连接微软服务超时或失败，请检查网络后手动刷新', 504) from None
    except (ValueError, UnicodeError):
        raise MailError('微软服务返回了无法解析的数据') from None


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script','style','head'):
            self.hidden += 1
        elif not self.hidden and tag in ('p','div','br','tr','li','hr'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style','head'):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ('p','div','tr','li'):
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_body(body):
    content = body.get('content', '')
    if body.get('contentType', '').lower() != 'html':
        return content
    parser = TextExtractor()
    parser.feed(content)
    return ''.join(parser.parts).strip()


def message_fields(item):
    sender = item.get('from', {}).get('emailAddress', {})
    return {'id':item.get('id',''), 'subject':item.get('subject') or '（无主题）',
            'sender':sender.get('name') or sender.get('address') or '未知发件人',
            'sender_address':sender.get('address',''), 'received_at':item.get('receivedDateTime',''),
            'preview':item.get('bodyPreview',''), 'is_read':item.get('isRead',False)}


class MailReader:
    def __init__(self, store):
        self.store = store
        self._tokens = {}
        self._locks = {}
        self._guard = threading.Lock()
        self._cooldown = {}

    def _lock(self, account_id):
        with self._guard:
            return self._locks.setdefault(account_id, threading.Lock())

    def _access_token(self, account_id):
        cached = self._tokens.get(account_id)
        if cached and cached[1] > time.monotonic() + 60:
            return cached[0]
        account = self.store.reveal(account_id)
        payload = urlencode({'client_id':account['client_id'], 'grant_type':'refresh_token',
                             'refresh_token':account['token'], 'scope':'https://graph.microsoft.com/.default'}).encode()
        result = request_json('https://login.microsoftonline.com/common/oauth2/v2.0/token', payload,
                              {'Content-Type':'application/x-www-form-urlencoded'})
        access = result.get('access_token')
        if not access:
            raise MailError('微软未返回访问令牌，请检查邮箱授权')
        # Persist a rotated refresh token before using it; stale writers cannot overwrite newer credentials.
        if result.get('refresh_token'):
            self.store.rotate_token(account_id, account['token'], result['refresh_token'])
        lifetime = max(0, int(result.get('expires_in', 3600)))
        self._tokens[account_id] = (access, time.monotonic() + lifetime)
        return access

    def _graph(self, account_id, path):
        with self._lock(account_id):
            remaining = self._cooldown.get(account_id, 0) - time.monotonic()
            if remaining > 0:
                raise MailError(f'请等待 {int(remaining) + 1} 秒后再刷新', 429, int(remaining) + 1)
            try:
                for attempt in range(2):
                    access = self._access_token(account_id)
                    try:
                        return request_json('https://graph.microsoft.com/v1.0' + path, headers={
                            'Authorization':'Bearer ' + access, 'Prefer':'outlook.body-content-type="text"'})
                    except MailError as error:
                        if error.status == 401:
                            self._tokens.pop(account_id, None)
                            if attempt == 0:
                                continue
                        raise
            except MailError as error:
                if error.status == 429:
                    self._cooldown[account_id] = time.monotonic() + (error.retry_after or 60)
                raise

    def messages(self, account_id):
        query = urlencode({'$top':'25', '$orderby':'receivedDateTime desc',
            '$select':'id,subject,from,receivedDateTime,bodyPreview,isRead'})
        result = self._graph(account_id, '/me/mailFolders/inbox/messages?' + query)
        email = self.store.reveal(account_id)['email']
        return {'email':email, 'messages':[message_fields(item) for item in result.get('value',[])],
                'has_more':bool(result.get('@odata.nextLink'))}

    def message(self, account_id, message_id):
        if not isinstance(message_id, str) or not message_id or len(message_id) > 4096:
            raise ValueError('邮件标识格式错误')
        query = urlencode({'$select':'id,subject,from,toRecipients,receivedDateTime,body,isRead'})
        item = self._graph(account_id, '/me/messages/' + quote(message_id, safe='') + '?' + query)
        return {**message_fields(item), 'body':plain_body(item.get('body',{})),
                'recipients':', '.join(r.get('emailAddress',{}).get('address','') for r in item.get('toRecipients',[]))}
