import json
import unittest
from unittest.mock import patch

from mail_reader import MailReader, MailError, plain_body
import test_app as fixtures
from test_app import LINE, TOKEN, PASSWORD


class MailTests(unittest.TestCase):
    tearDown = fixtures.StoreTests.tearDown
    def setUp(self):
        fixtures.StoreTests.setUp(self)
        self.store.import_text(LINE, 'mail test')
        self.account_id = self.store.accounts()['items'][0]['id']
        self.reader = MailReader(self.store)

    def test_on_demand_token_rotation_cache_and_body(self):
        self.assertEqual(self.reader._tokens, {})
        listing = {'value':[{'id':'message/id', 'subject':'Test', 'from':{'emailAddress':{'name':'Sender','address':'sender@example.com'}}, 'receivedDateTime':'2026-10-16T00:00:00Z', 'isRead':False,'bodyPreview':'Hello'}]}
        with patch('mail_reader.request_json', side_effect=[{'access_token':'ACCESS_SECRET','expires_in':3600,'refresh_token':'ROTATED_SECRET'}, listing, {'subject':'Test','body':{'contentType':'html','content':'<p>Hello</p><script>bad()</script><p>World</p>'}}]) as remote:
            result = self.reader.messages(self.account_id)
            self.assertEqual(result['messages'][0]['subject'], 'Test')
            self.assertEqual(remote.call_count,2)
            self.assertEqual(self.store.reveal(self.account_id)['token'],'ROTATED_SECRET')
            self.assertEqual(self.store.reveal(self.account_id)['password'],PASSWORD)
            detail = self.reader.message(self.account_id,'message/id')
            self.assertIn('World',detail['body'])
            self.assertNotIn('bad()',detail['body'])
            self.assertEqual(remote.call_count,3)
            self.assertIn('message%2Fid',remote.call_args.args[0])
            self.assertNotIn('ACCESS_SECRET',json.dumps(result))

    def test_auth_failure_and_throttle_are_safe(self):
        with patch('mail_reader.request_json',side_effect=MailError('Authorization failed',401)):
            with self.assertRaises(MailError):self.reader.messages(self.account_id)
        self.assertEqual(self.store.reveal(self.account_id)['token'], TOKEN)
        self.assertEqual(self.reader._tokens,{})

    def test_throttle_does_not_retry_or_poll(self):
        self.reader._tokens[self.account_id] = ('ACCESS', __import__('time').monotonic() + 3600)
        with patch('mail_reader.request_json',side_effect=MailError('throttled',429,60)) as remote:
            for _ in range(2):
                with self.assertRaises(MailError) as error:self.reader.messages(self.account_id)
                self.assertEqual(error.exception.status,429)
            self.assertEqual(remote.call_count,1)

    def test_expired_access_refreshes_once(self):
        self.reader._tokens[self.account_id] = ('OLD_ACCESS', __import__('time').monotonic()+3600)
        with patch('mail_reader.request_json',side_effect=[MailError('expired',401),{'access_token':'NEW_ACCESS','expires_in':3600},{'value':[]}]) as remote:
            self.assertEqual(self.reader.messages(self.account_id)['messages'],[])
            self.assertEqual(remote.call_count,3)

    def test_rotation_compare_and_swap(self):
        self.store.rotate_token(self.account_id,TOKEN,'NEW')
        self.store.rotate_token(self.account_id,TOKEN,'STALE')
        self.assertEqual(self.store.reveal(self.account_id)['token'],'NEW')

    def test_text_and_html_body(self):
        self.assertEqual(plain_body({'contentType':'text','content':'<literal>Code: 123456'}),'<literal>Code: 123456')
        result=plain_body({'contentType':'html','content':'<style>hidden</style><p>Code &amp; text</p><script>evil</script>'})
        self.assertIn('Code & text',result)
        self.assertNotIn('evil',result)
        self.assertNotIn('hidden',result)


class MailApiTests(unittest.TestCase):
    setUp = fixtures.ApiTests.setUp
    tearDown = fixtures.ApiTests.tearDown
    request = fixtures.ApiTests.request
    def test_email_routes_require_session_and_return_only_message_data(self):
        self.store.import_text(LINE,'test')
        account_id=self.store.accounts()['items'][0]['id']
        from urllib.error import HTTPError
        with self.assertRaises(HTTPError) as error:
            self.request('/api/mail/list',{'id':account_id})
        self.assertEqual(error.exception.code,403)
        with patch('mail_reader.MailReader.messages',return_value={'email':'demo@example.com','messages':[]} ) as fetch:
            result=self.request('/api/mail/list',{'id':account_id},{'X-Session-Token':'test-session'})
            self.assertEqual(result['messages'],[])
            fetch.assert_called_once_with(account_id)
        with patch('mail_reader.MailReader.message',return_value={'subject':'test','body':'body'}) as fetch:
            result=self.request('/api/mail/message',{'id':account_id,'message_id':'abc'},{'X-Session-Token':'test-session'})
            self.assertEqual(result['body'],'body')
            fetch.assert_called_once_with(account_id,'abc')

if __name__=='__main__':unittest.main()
