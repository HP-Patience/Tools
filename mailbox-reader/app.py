"""Local mailbox credential importer. Run: python app.py"""
import ctypes
import errno
from contextlib import contextmanager
from ctypes import wintypes
import json
import hashlib
import hmac
import time
from http.cookies import SimpleCookie
import mimetypes
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import uuid
import webbrowser
from mail_reader import MailReader, MailError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse, unquote

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 5 * 1024 * 1024
MAX_LINES = 10000
ACCOUNT_STATUSES = ('alive', 'banned')
ACCOUNT_OWNERS = ('\u5929\u9009', '3080', '3090')


def parse_text(text):
    if not isinstance(text, str):
        raise ValueError("导入内容必须是文本")
    if len(text.encode('utf-8')) > MAX_BYTES:
        raise ValueError("文本不能超过 5 MiB")
    lines = text.removeprefix('\ufeff').splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("每次最多导入 10000 行")
    rows, seen = [], set()
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        parts = line.split('----', 3)
        row = {'line': number, 'email': '', 'status': 'invalid', 'reason': ''}
        if len(parts) != 4:
            row['reason'] = '需要四个字段，以 ---- 分隔'
        else:
            email, password, client_id, token = parts
            email = email.strip()
            client_id = client_id.strip()
            row['email'] = email
            if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
                row['reason'] = '邮箱地址格式错误'
            elif not password.strip() or not token.strip():
                row['reason'] = '密码和 Token 不能为空'
            else:
                try:
                    uuid.UUID(client_id)
                except ValueError:
                    row['reason'] = 'Client ID 必须是 UUID 格式'
                else:
                    row.update(password=password, client_id=client_id, token=token)
                    key = email.casefold()
                    if key in seen:
                        row.update(status='duplicate', reason='本次文本中邮箱重复')
                    else:
                        seen.add(key)
                        row.update(status='valid', reason='可导入')
        rows.append(row)
    return rows


class Blob(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_ubyte))]


def crypt(value, decrypt=False):
    if sys.platform != 'win32':
        key = os.environ.get('MAILBOX_ENCRYPTION_KEY', '')
        if not key:
            raise RuntimeError('Linux 部署必须设置 MAILBOX_ENCRYPTION_KEY')
        try:
            raw_key = key.encode('utf-8')
            if decrypt:
                if len(value) < 16 + 16 + 32 or not value.startswith(b'MR1'):
                    raise ValueError('密文格式无效')
                salt, iv, tag, ciphertext = value[3:19], value[19:35], value[35:67], value[67:]
                derived = hashlib.pbkdf2_hmac('sha256', raw_key, salt, 200000, 64)
                if not hmac.compare_digest(tag, hmac.new(derived[32:], value[:35] + ciphertext, hashlib.sha256).digest()):
                    raise ValueError('密文校验失败')
            else:
                salt, iv = os.urandom(16), os.urandom(16)
                derived = hashlib.pbkdf2_hmac('sha256', raw_key, salt, 200000, 64)
            command = ['openssl', 'enc', '-aes-256-cbc', '-K', derived[:32].hex(), '-iv', iv.hex()]
            if decrypt:
                command.append('-d')
            result = subprocess.run(command, input=ciphertext if decrypt else value, capture_output=True, check=False)
            if result.returncode != 0:
                raise ValueError('OpenSSL 无法处理凭据')
            if decrypt:
                return result.stdout
            payload = b'MR1' + salt + iv + result.stdout
            return payload[:35] + hmac.new(derived[32:], payload, hashlib.sha256).digest() + result.stdout
        except (OSError, ValueError) as error:
            raise RuntimeError('Linux 凭据加密失败，请检查 OpenSSL 和 MAILBOX_ENCRYPTION_KEY') from error
    source = ctypes.create_string_buffer(value)
    incoming = Blob(len(value), ctypes.cast(source, ctypes.POINTER(ctypes.c_ubyte)))
    outgoing = Blob()
    api = ctypes.WinDLL('crypt32', use_last_error=True)
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if decrypt:
        fn = api.CryptUnprotectData
        fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing))
    else:
        fn = api.CryptProtectData
        fn.argtypes = [ctypes.POINTER(Blob), wintypes.LPCWSTR, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
        ok = fn(ctypes.byref(incoming), 'Mailbox credentials', None, None, None, 1, ctypes.byref(outgoing))
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        kernel.LocalFree(outgoing.pbData)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL, email_key TEXT NOT NULL UNIQUE,
                    credentials BLOB NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
                CREATE TABLE IF NOT EXISTS imports (
                    id INTEGER PRIMARY KEY, source TEXT NOT NULL, imported INTEGER NOT NULL,
                    duplicates INTEGER NOT NULL, invalid INTEGER NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                );
            ''')
            columns = {row['name'] for row in db.execute('PRAGMA table_info(accounts)')}
            if 'status' not in columns:
                db.execute("ALTER TABLE accounts ADD COLUMN status TEXT NOT NULL DEFAULT 'alive' CHECK(status IN ('alive','banned'))")
            if 'owner' not in columns:
                db.execute("ALTER TABLE accounts ADD COLUMN owner TEXT NOT NULL DEFAULT '' CHECK(owner IN ('','\u5929\u9009','3080','3090'))")

            db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))")
            db.execute("CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE CHECK(length(trim(name)) BETWEEN 1 AND 60))")
            db.execute("CREATE TABLE IF NOT EXISTS project_accounts (project_id INTEGER NOT NULL REFERENCES projects(id), account_id INTEGER NOT NULL REFERENCES accounts(id), status TEXT NOT NULL DEFAULT 'alive' CHECK(status IN ('alive','banned')), owner TEXT NOT NULL DEFAULT '' CHECK(owner IN ('','天选','3080','3090')), PRIMARY KEY(project_id,account_id))")
            db.execute("CREATE TABLE IF NOT EXISTS migrations (name TEXT PRIMARY KEY)")
            if not db.execute("SELECT 1 FROM migrations WHERE name='projects-v1'").fetchone():
                db.execute("INSERT INTO projects(id,name) VALUES(1,'Arena项目')")
                db.execute("INSERT INTO project_accounts(project_id,account_id,status,owner) SELECT 1,id,status,owner FROM accounts")
                db.execute("INSERT INTO migrations(name) VALUES('projects-v1')")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def hash_password(password):
        if not isinstance(password, str) or len(password) < 8:
            raise ValueError('密码至少需要 8 个字符')
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 260000)
        return salt.hex() + ':' + digest.hex()

    def has_users(self):
        with self.connect() as db:
            return db.execute('SELECT 1 FROM users LIMIT 1').fetchone() is not None

    def create_user(self, username, password):
        if not isinstance(username, str) or not re.fullmatch(r'[A-Za-z0-9_.@-]{3,80}', username):
            raise ValueError('用户名需为 3 至 80 个字母、数字或常用符号')
        password_hash = self.hash_password(password)
        with self.connect() as db:
            try:
                db.execute('INSERT INTO users(username,password_hash) VALUES(?,?)', (username, password_hash))
            except sqlite3.IntegrityError:
                raise ValueError('用户名已存在') from None
        return {'username': username}

    def verify_user(self, username, password):
        with self.connect() as db:
            row = db.execute('SELECT password_hash FROM users WHERE username=?', (username,)).fetchone()
        if not row or ':' not in row['password_hash']:
            return False
        salt, expected = row['password_hash'].split(':', 1)
        try:
            actual = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(salt), 260000).hex()
        except (TypeError, ValueError):
            return False
        return hmac.compare_digest(actual, expected)

    def preview(self, text):
        rows = parse_text(text)
        with self.connect() as db:
            existing = {r[0] for r in db.execute('SELECT email_key FROM accounts')}
        for row in rows:
            if row['status'] == 'valid' and row['email'].casefold() in existing:
                row.update(status='duplicate', reason='账号已存在，将跳过')
        return rows

    def import_text(self, text, source, project_id=1):
        rows = parse_text(text)
        counts = {'imported': 0, 'duplicates': 0, 'invalid': 0}
        with self.connect() as db:
            self.require_project(db, project_id)
            for row in rows:
                if row['status'] != 'valid':
                    counts['duplicates' if row['status'] == 'duplicate' else 'invalid'] += 1
                    continue
                payload = {key: row[key] for key in ('password', 'client_id', 'token')}
                encrypted = crypt(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
                cursor = db.execute('INSERT OR IGNORE INTO accounts(email,email_key,credentials) VALUES(?,?,?)',
                                    (row['email'], row['email'].casefold(), encrypted))
                counts['imported' if cursor.rowcount else 'duplicates'] += 1
                account_id = db.execute('SELECT id FROM accounts WHERE email_key=?', (row['email'].casefold(),)).fetchone()[0]
                if project_id:
                    db.execute('INSERT OR IGNORE INTO project_accounts(project_id,account_id) VALUES(?,?)', (project_id,account_id))
            db.execute('INSERT INTO imports(source,imported,duplicates,invalid) VALUES(?,?,?,?)',
                       (source[:200], counts['imported'], counts['duplicates'], counts['invalid']))
        return counts

    @staticmethod
    def account_filter(search='', status='', owner=''):
        if status and status not in ACCOUNT_STATUSES:
            raise ValueError('\u72b6\u6001\u9009\u9879\u65e0\u6548')
        if owner and owner not in (*ACCOUNT_OWNERS, 'unassigned'):
            raise ValueError('\u5f52\u5c5e\u9009\u9879\u65e0\u6548')
        pattern = '%' + search.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        clauses, values = ["email LIKE ? ESCAPE '\\'"], [pattern]
        if status:
            clauses.append('status = ?')
            values.append(status)
        if owner:
            clauses.append('owner = ?')
            values.append('' if owner == 'unassigned' else owner)
        return ' AND '.join(clauses), values

    @staticmethod
    def require_project(db, project_id, allow_all=True):
        if type(project_id) is not int or project_id < 0 or (not allow_all and not project_id):
            raise ValueError('项目无效')
        if project_id and not db.execute('SELECT 1 FROM projects WHERE id=?', (project_id,)).fetchone():
            raise ValueError('项目不存在')

    def projects(self):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT p.id,p.name,count(pa.account_id) AS count FROM projects p LEFT JOIN project_accounts pa ON pa.project_id=p.id GROUP BY p.id ORDER BY p.id')]

    def create_project(self, name):
        if not isinstance(name,str) or not 1 <= len(name.strip()) <= 60:
            raise ValueError('项目名称需为 1 至 60 个字符')
        with self.connect() as db:
            try:
                cursor = db.execute('INSERT INTO projects(name) VALUES(?)', (name.strip(),))
            except sqlite3.IntegrityError:
                raise ValueError('项目名称已存在') from None
            return {'id': cursor.lastrowid, 'name': name.strip()}

    @staticmethod
    def validate_ids(ids):
        if not isinstance(ids,list) or not ids or len(ids)>100000 or any(type(i) is not int or i<=0 for i in ids):
            raise ValueError('请选择 1 至 100000 个有效账号')
        return list(dict.fromkeys(ids))

    def assign_project(self, ids, project_id, remove=False):
        ids = self.validate_ids(ids)
        if type(remove) is not bool:
            raise ValueError('项目操作无效')
        with self.connect() as db:
            self.require_project(db,project_id,False)
            for account_id in ids:
                if not db.execute('SELECT 1 FROM accounts WHERE id=?',(account_id,)).fetchone():
                    raise LookupError('账号不存在')
                if remove:
                    db.execute('DELETE FROM project_accounts WHERE project_id=? AND account_id=?',(project_id,account_id))
                else:
                    db.execute('INSERT OR IGNORE INTO project_accounts(project_id,account_id) VALUES(?,?)',(project_id,account_id))
        return {'updated':len(ids)}

    @staticmethod
    def account_source(project_id):
        # Legacy columns are retained for rollback; all project writes use project_accounts.
        if project_id:
            return "(SELECT a.id,a.email,a.created_at,pa.status,pa.owner FROM accounts a JOIN project_accounts pa ON pa.account_id=a.id WHERE pa.project_id=?)", [project_id]
        return "(SELECT id,email,created_at,'' AS status,'' AS owner FROM accounts)", []

    def account_ids(self, search='', status='', owner='', project_id=1):
        where, values = self.account_filter(search,status,owner)
        source, params = self.account_source(project_id)
        with self.connect() as db:
            self.require_project(db,project_id)
            return [row[0] for row in db.execute('SELECT id FROM '+source+' WHERE '+where+' ORDER BY id', (*params,*values))]

    def accounts(self, search='', page=1, status='', owner='', order='asc', project_id=1):
        if order not in ('asc','desc'):
            raise ValueError('排序选项无效')
        where, values = self.account_filter(search,status,owner)
        source, params = self.account_source(project_id)
        with self.connect() as db:
            self.require_project(db,project_id)
            total = db.execute('SELECT count(*) FROM accounts').fetchone()[0]
            matched = db.execute('SELECT count(*) FROM '+source+' WHERE '+where, (*params,*values)).fetchone()[0]
            page = max(1,min(page,max(1,(matched+49)//50)))
            rows = db.execute('SELECT * FROM '+source+' WHERE '+where+' ORDER BY id '+order.upper()+' LIMIT 50 OFFSET ?', (*params,*values,(page-1)*50)).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                item['projects'] = [dict(p) for p in db.execute('SELECT p.id,p.name FROM projects p JOIN project_accounts pa ON pa.project_id=p.id WHERE pa.account_id=? ORDER BY p.id',(row['id'],))]
                items.append(item)
        return {'total':total,'matched':matched,'items':items,'page':page}

    def update_account(self, account_id, values, project_id=1):
        self.bulk_update_accounts([account_id],values,project_id)
        return {'ok':True}

    def bulk_update_accounts(self, ids, values, project_id=1):
        ids = self.validate_ids(ids)
        if not isinstance(values,dict) or not values or set(values)-{'status','owner'}:
            raise ValueError('只能修改状态和归属')
        if 'status' in values and values['status'] not in ACCOUNT_STATUSES:
            raise ValueError('状态选项无效')
        if 'owner' in values and values['owner'] not in ('',*ACCOUNT_OWNERS):
            raise ValueError('归属选项无效')
        assignments = ', '.join(key+' = ?' for key in values)
        with self.connect() as db:
            self.require_project(db,project_id,False)
            for offset in range(0,len(ids),500):
                batch = ids[offset:offset+500]
                placeholders = ','.join('?' for _ in batch)
                cursor = db.execute('UPDATE project_accounts SET '+assignments+' WHERE project_id=? AND account_id IN ('+placeholders+')',(*values.values(),project_id,*batch))
                if cursor.rowcount != len(batch):
                    raise LookupError('部分账号不属于当前项目，本次修改已回滚')
        return {'updated':len(ids)}

    def reveal(self, account_id):
        with self.connect() as db:
            row = db.execute('SELECT * FROM accounts WHERE id=?', (account_id,)).fetchone()
        if not row:
            raise LookupError('账号不存在')
        return {'email': row['email'], **json.loads(crypt(row['credentials'], decrypt=True))}

    def rotate_token(self, account_id, old_token, new_token):
        with self.connect() as db:
            row = db.execute('SELECT credentials FROM accounts WHERE id=?', (account_id,)).fetchone()
            if not row:
                raise LookupError('账号不存在')
            payload = json.loads(crypt(row['credentials'], decrypt=True))
            if payload['token'] != old_token:
                return
            payload['token'] = new_token
            encrypted = crypt(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
            db.execute('UPDATE accounts SET credentials=? WHERE id=? AND credentials=?', (encrypted, account_id, row['credentials']))

    def history(self):
        with self.connect() as db:
            return [dict(r) for r in db.execute('SELECT * FROM imports ORDER BY id DESC LIMIT 20')]


def public_rows(rows):
    return [{k: v for k, v in row.items() if k in ('line', 'email', 'status', 'reason')} for row in rows]


def make_handler(store, csrf_token, auth_enabled=False):
    mail = MailReader(store)
    sessions = {}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            pass  # Credential-related requests are never logged.

        def send(self, status, body, content_type='application/json; charset=utf-8'):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(body)

        def trusted(self):
            host = self.headers.get('Host', '').split(':', 1)[0]
            allowed_hosts = {'127.0.0.1', 'localhost'}
            allowed_hosts.update(item.strip() for item in os.environ.get('MAILBOX_ALLOWED_HOSTS', '').split(',') if item.strip())
            origin = self.headers.get('Origin')
            origin_host = urlparse(origin).hostname if origin else None
            return host in allowed_hosts and (origin_host is None or origin_host in allowed_hosts)

        def session_id(self):
            cookie = SimpleCookie(self.headers.get('Cookie', ''))
            morsel = cookie.get('mailroom_session')
            return morsel.value if morsel else ''

        def authenticated(self):
            if not auth_enabled:
                return True
            session = sessions.get(self.session_id())
            return bool(session and session['expires'] > time.time())

        def require_auth(self):
            if not self.authenticated():
                self.send(401, {'error': '请先登录', 'authenticated': False})
                return False
            return True

        def do_GET(self):
            if not self.trusted():
                return self.send(403, {'error': '请求来源不允许'})
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == '/api/session':
                    return self.send(200, {'token': csrf_token, 'auth_enabled': auth_enabled, 'authenticated': self.authenticated(), 'setup_required': auth_enabled and not store.has_users()})
                if auth_enabled and parsed.path.startswith('/api/') and parsed.path not in ('/api/session', '/api/auth/login', '/api/auth/setup') and not self.require_auth():
                    return
                if parsed.path == '/api/session':
                    return self.send(200, {'token': csrf_token, 'auth_enabled': auth_enabled, 'authenticated': self.authenticated(), 'setup_required': auth_enabled and not store.has_users()})
                if parsed.path == '/api/projects':
                    return self.send(200, store.projects())
                if parsed.path == '/api/accounts':
                    page = max(1, int(query.get('page', ['1'])[0]))
                    return self.send(200, store.accounts(query.get('q', [''])[0][:200], page, query.get('status', [''])[0], query.get('owner', [''])[0], query.get('order', ['asc'])[0], int(query.get('project_id', ['1'])[0])))
                if parsed.path == '/api/accounts/ids':
                    return self.send(200, {'ids': store.account_ids(query.get('q', [''])[0][:200], query.get('status', [''])[0], query.get('owner', [''])[0], int(query.get('project_id', ['1'])[0]))})
                if parsed.path == '/api/history':
                    return self.send(200, store.history())
                static_root = (ROOT / 'dist').resolve()
                relative = 'index.html' if parsed.path == '/' else unquote(parsed.path).lstrip('/')
                file = (static_root / relative).resolve()
                if not file.is_relative_to(static_root) or not file.is_file():
                    return self.send(404, {'error': '页面不存在，请先执行 npm run build'})
                mime = {'.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.html': 'text/html'}.get(file.suffix, mimetypes.guess_type(file.name)[0] or 'application/octet-stream')
                self.send(200, file.read_bytes(), mime + ('; charset=utf-8' if mime.startswith('text/') else ''))
            except ValueError:
                self.send(400, {'error': '请求参数错误'})
            except Exception:
                self.send(500, {'error': '读取失败，请检查本地数据文件权限'})

        def login_session(self, username):
            session_id = secrets.token_urlsafe(32)
            sessions[session_id] = {'username': username, 'expires': time.time() + 86400 * 7}
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Set-Cookie', f'mailroom_session={session_id}; HttpOnly; SameSite=Strict; Path=/; Max-Age=604800')
            body = json.dumps({'authenticated': True, 'username': username}, ensure_ascii=False).encode()
            self.send_header('Content-Length', str(len(body)))
            self.end_headers(); self.wfile.write(body)

        def do_POST(self):
            if not self.trusted():
                return self.send(403, {'error': '请求来源不允许'})
            if self.path == '/api/auth/setup' and auth_enabled:
                pass
            elif self.path == '/api/auth/login' and auth_enabled:
                pass
            elif auth_enabled and not self.require_auth():
                return
            elif not secrets.compare_digest(self.headers.get('X-Session-Token', ''), csrf_token):
                return self.send(403, {'error': '会话已失效，请刷新页面'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > MAX_BYTES * 6 + 1024:
                    return self.send(413, {'error': '请求过大或为空'})
                data = json.loads(self.rfile.read(length).decode('utf-8'))
                if not isinstance(data, dict):
                    raise ValueError('请求格式错误')
                if self.path == '/api/auth/setup' and auth_enabled:
                    if store.has_users():
                        return self.send(400, {'error': '管理员账号已初始化'})
                    store.create_user(data.get('username', ''), data.get('password', ''))
                    return self.login_session(data.get('username', ''))
                if self.path == '/api/auth/login' and auth_enabled:
                    username, password = data.get('username', ''), data.get('password', '')
                    if not store.verify_user(username, password):
                        return self.send(401, {'error': '用户名或密码错误'})
                    return self.login_session(username)
                if self.path == '/api/projects/create':
                    return self.send(200, store.create_project(data.get('name')))
                if self.path == '/api/projects/assign':
                    return self.send(200, store.assign_project(data.get('ids'), data.get('project_id'), data.get('remove',False)))
                if self.path == '/api/mail/list':
                    return self.send(200, mail.messages(int(data.get('id', 0))))
                if self.path == '/api/mail/message':
                    return self.send(200, mail.message(int(data.get('id', 0)), data.get('message_id')))
                if self.path == '/api/preview':
                    rows = store.preview(data.get('text'))
                    return self.send(200, {'rows': public_rows(rows), 'counts': {s: sum(r['status'] == s for r in rows) for s in ('valid', 'duplicate', 'invalid')}})
                if self.path == '/api/import':
                    source = data.get('source', '粘贴文本')
                    if not isinstance(source, str):
                        raise ValueError('来源名称格式错误')
                    return self.send(200, store.import_text(data.get('text'), source, data.get('project_id',1)))
                if self.path == '/api/accounts/bulk-update':
                    return self.send(200, store.bulk_update_accounts(data.get('ids'), data.get('values'), data.get('project_id',1)))
                if self.path == '/api/account/update':
                    return self.send(200, store.update_account(int(data.get('id', 0)), {key: value for key, value in data.items() if key not in ('id','project_id')}, data.get('project_id',1)))
                if self.path == '/api/reveal':
                    return self.send(200, store.reveal(int(data.get('id', 0))))
                self.send(404, {'error': '接口不存在'})
            except MailError as exc:
                self.send(exc.status, {'error': str(exc), 'retry_after': exc.retry_after})
            except (ValueError, TypeError, UnicodeError) as exc:
                self.send(400, {'error': str(exc) if isinstance(exc, ValueError) else '请求格式错误'})
            except LookupError:
                self.send(404, {'error': '账号不存在或不属于当前项目'})
            except Exception:
                self.send(500, {'error': '操作失败。请确认当前 Windows 用户可解密数据，且数据库可写；本次导入已回滚。'})
    return Handler


def bind_server(handler, preferred_port=48371, host='127.0.0.1'):
    if not 0 <= preferred_port <= 65535:
        raise ValueError('端口必须在 0 到 65535 之间')
    try:
        return ThreadingHTTPServer((host, preferred_port), handler)
    except OSError as error:
        if error.errno not in (errno.EADDRINUSE, errno.EACCES) and getattr(error, 'winerror', None) not in (10048, 10013):
            raise
        return ThreadingHTTPServer((host, 0), handler)


if __name__ == '__main__':
    if sys.platform != 'win32' and not os.environ.get('MAILBOX_ENCRYPTION_KEY'):
        raise SystemExit('Linux 运行前请设置 MAILBOX_ENCRYPTION_KEY；Windows 使用 DPAPI。')
    port = int(os.environ.get('MAILBOX_PORT', '48371'))
    store = Store(ROOT / 'data' / 'mailboxes.sqlite3')
    auth_enabled = os.environ.get('MAILBOX_AUTH', '1') != '0'
    host = os.environ.get('MAILBOX_HOST', '127.0.0.1')
    server = bind_server(make_handler(store, secrets.token_urlsafe(32), auth_enabled), port, host)
    port = server.server_port
    if '--report-port' in sys.argv:
        print(json.dumps({'mailroom_port': port}), flush=True)
    if '--open' in sys.argv:
        webbrowser.open(f'http://127.0.0.1:{port}')
    print(f'邮箱解析服务已启动：http://127.0.0.1:{port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
