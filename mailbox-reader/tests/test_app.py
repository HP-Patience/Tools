import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app import MAX_BYTES, Store, crypt, make_handler, parse_text, public_rows
from http.server import ThreadingHTTPServer

CLIENT = '00000000-0000-4000-8000-000000000001'
PASSWORD = '  P@ss!*$中文  '
TOKEN = ' M.C548!foo*bar$$----tail  '
LINE = f'demo@example.com----{PASSWORD}----{CLIENT}----{TOKEN}'


class ParserTests(unittest.TestCase):
    def test_bom_blank_and_exact_credentials(self):
        rows = parse_text('\ufeff\r\n' + LINE + '\r\n\n')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['line'], 2)
        self.assertEqual(rows[0]['password'], PASSWORD)
        self.assertEqual(rows[0]['token'], TOKEN)
        self.assertEqual(rows[0]['status'], 'valid')

    def test_errors_and_case_insensitive_duplicates(self):
        rows = parse_text('\n'.join(['invalid', 'bad----p----bad----t', LINE, LINE.replace('demo@', 'DEMO@'), f'x@example.com----p----bad----t', f'x@example.com--------{CLIENT}----t']))
        self.assertEqual([r['status'] for r in rows], ['invalid','invalid','valid','duplicate','invalid','invalid'])
        self.assertNotIn('password', json.dumps(public_rows(rows)))
        self.assertNotIn(PASSWORD, json.dumps(public_rows(rows), ensure_ascii=False))

    def test_limits(self):
        for value in (None, 'x' * (MAX_BYTES + 1), '\n' * 10001):
            with self.assertRaises(ValueError): parse_text(value)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_encryption_persistence_and_duplicates(self):
        result = self.store.import_text(LINE + '\ninvalid\n' + LINE.upper(), 'test.txt')
        self.assertEqual(result, {'imported':1, 'duplicates':1, 'invalid':1})
        store = Store(self.path)
        account = store.accounts()['items'][0]
        self.assertNotIn('credentials', account)
        revealed = store.reveal(account['id'])
        self.assertEqual(revealed['password'], PASSWORD)
        self.assertEqual(revealed['token'], TOKEN)
        self.assertEqual(store.preview(LINE)[0]['status'], 'duplicate')
        self.assertEqual(store.import_text(LINE.replace(PASSWORD,'NEW'), 'second')['duplicates'], 1)
        self.assertEqual(store.reveal(account['id'])['password'], PASSWORD)
        self.assertEqual(len(store.history()), 2)
        with closing(sqlite3.connect(self.path)) as db:
            blob = db.execute('SELECT credentials FROM accounts').fetchone()[0]
        self.assertNotIn(PASSWORD.encode(), blob)
        self.assertNotIn(TOKEN.encode(), blob)
        self.assertEqual(crypt(crypt(b'exact\x00bytes'), True), b'exact\x00bytes')

    def test_metadata_filters_and_persistence(self):
        self.store.import_text('\n'.join(LINE.replace('demo@', name + '@') for name in ('one','two','three','four')), 'test')
        accounts = {r['email'].split('@')[0]: r for r in self.store.accounts()['items']}
        self.assertTrue(all(r['status'] == 'alive' and r['owner'] == '' for r in accounts.values()))
        self.store.update_account(accounts['one']['id'], {'status':'banned', 'owner':'天选'})
        self.store.update_account(accounts['two']['id'], {'owner':'3080'})
        self.store.update_account(accounts['three']['id'], {'owner':'3090'})
        self.assertEqual(self.store.accounts(status='banned')['matched'], 1)
        for owner in ('天选','3080','3090','unassigned'):
            self.assertEqual(self.store.accounts(owner=owner)['matched'], 1)
        self.assertEqual(self.store.accounts(status='alive', owner='天选')['matched'], 0)
        self.assertEqual(self.store.accounts(search='one', status='banned', owner='天选')['matched'], 1)
        self.store.import_text(LINE.replace('demo@','one@'), 'duplicate')
        reopened = Store(self.path)
        row = reopened.accounts(owner='天选')['items'][0]
        self.assertEqual((row['id'], row['status']), (accounts['one']['id'], 'banned'))
        self.assertEqual(reopened.reveal(row['id'])['password'], PASSWORD)
        reopened.update_account(row['id'], {'owner':''})
        self.assertEqual(reopened.accounts(owner='unassigned')['matched'], 2)

    def test_sorting_and_bulk_updates(self):
        self.store.import_text('\n'.join(LINE.replace('demo@', f'bulk{i}@') for i in range(52)), 'bulk')
        first = self.store.accounts()
        self.assertEqual([r['id'] for r in first['items']], list(range(1,51)))
        self.assertEqual(self.store.accounts(page=2)['items'][0]['id'], 51)
        self.assertEqual(self.store.accounts(order='desc')['items'][0]['id'], 52)
        self.assertEqual(self.store.accounts(order='desc', page=2)['items'][-1]['id'], 1)
        with self.assertRaises(ValueError): self.store.accounts(order='drop table accounts')
        result = self.store.bulk_update_accounts([1,2,2,52], {'status':'banned','owner':'3090'})
        self.assertEqual(result['updated'], 3)
        self.assertEqual(self.store.account_ids(status='banned', owner='3090'), [1,2,52])
        self.assertEqual(self.store.accounts(status='banned', order='desc')['items'][0]['id'],52)
        self.assertEqual(self.store.reveal(1)['password'], PASSWORD)
        for ids, values in (([], {'status':'alive'}), ([True], {'status':'alive'}), (['1'], {'owner':'3080'}), ([1], {'owner':'4090'}), ([1], {}), ([1], None)):
            with self.assertRaises(ValueError): self.store.bulk_update_accounts(ids, values)
        with self.assertRaises(LookupError): self.store.bulk_update_accounts([1,999999], {'status':'alive'})
        self.assertEqual(self.store.account_ids(status='banned'),[1,2,52])

    def test_bulk_chunks_rollback_atomically(self):
        with self.store.connect() as db:
            db.executemany('INSERT INTO accounts(email,email_key,credentials) VALUES(?,?,?)', [(f'chunk{i}@example.com', f'chunk{i}@example.com', b'unused') for i in range(501)])
        self.store.assign_project(list(range(1,502)),1)
        ids = self.store.account_ids()
        with self.assertRaises(LookupError): self.store.bulk_update_accounts(ids + [99999], {'status':'banned'})
        self.assertEqual(self.store.accounts(status='banned')['matched'], 0)
        self.assertEqual(self.store.bulk_update_accounts(ids, {'owner':'3080'})['updated'],501)
        self.assertEqual(self.store.accounts(owner='3080')['matched'],501)

    def test_metadata_validation(self):
        self.store.import_text(LINE, 'test')
        account_id = self.store.accounts()['items'][0]['id']
        for values in ({'status':'invalid'}, {'owner':'4090'}, {'owner':None}, {'password':'changed'}, {}):
            with self.assertRaises(ValueError): self.store.update_account(account_id, values)
        with self.assertRaises(LookupError): self.store.update_account(9999, {'status':'alive'})
        with self.assertRaises(ValueError): self.store.accounts(status='invalid')
        with self.assertRaises(ValueError): self.store.accounts(owner='4090')
        self.assertEqual(self.store.reveal(account_id)['password'], PASSWORD)

    def test_legacy_schema_migration_preserves_credentials(self):
        legacy_path = Path(self.temp.name) / 'legacy.sqlite3'
        payload = crypt(json.dumps({'password':PASSWORD, 'client_id':CLIENT, 'token':TOKEN}).encode())
        with closing(sqlite3.connect(legacy_path)) as db:
            db.execute('CREATE TABLE accounts (id INTEGER PRIMARY KEY, email TEXT NOT NULL, email_key TEXT NOT NULL UNIQUE, credentials BLOB NOT NULL, created_at TEXT NOT NULL)')
            db.execute('INSERT INTO accounts VALUES(7,?,?,?,?)', ('legacy@example.com','legacy@example.com',payload,'2026-10-16T00:00:00Z'))
            db.commit()
        migrated = Store(legacy_path)
        row = migrated.accounts()['items'][0]
        self.assertEqual((row['id'],row['status'],row['owner']), (7,'alive',''))
        self.assertEqual(migrated.reveal(7)['token'], TOKEN)
        self.assertEqual(Store(legacy_path).accounts()['total'], 1)

    def test_filtered_page_is_clamped_after_updates(self):
        self.store.import_text('\n'.join(LINE.replace('demo@', f'page{i}@') for i in range(51)), 'pages')
        result = self.store.accounts(page=2, status='alive')
        self.assertEqual(len(result['items']), 1)
        self.store.update_account(result['items'][0]['id'], {'status':'banned'})
        result = self.store.accounts(page=2, status='alive')
        self.assertEqual((result['matched'],result['page'],len(result['items'])), (50,1,50))

    def test_search_treats_wildcards_as_literal(self):
        self.store.import_text(LINE, 'test')
        self.assertEqual(self.store.accounts('demo')['matched'],1)
        self.assertEqual(self.store.accounts('%')['matched'],0)
        self.assertEqual(self.store.accounts('_')['matched'],0)

    def test_rollback_on_encryption_failure(self):
        from unittest.mock import patch
        with patch('app.crypt', side_effect=[b'encrypted', RuntimeError('failed')]):
            with self.assertRaises(RuntimeError):
                self.store.import_text(LINE + '\n' + LINE.replace('demo@','other@'), 'test')
        self.assertEqual(self.store.accounts()['total'], 0)
        self.assertEqual(self.store.history(), [])


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / 'api.sqlite3')
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(self.store, 'test-session'))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self, path, body=None, headers=None):
        data = None if body is None else json.dumps(body).encode()
        request = Request(self.url + path, data=data, headers=headers or {})
        with urlopen(request) as response:
            self.assertEqual(response.headers['Cache-Control'], 'no-store')
            return json.load(response)

    def test_complete_flow(self):
        self.assertEqual(self.request('/api/session')['token'], 'test-session')
        headers = {'X-Session-Token':'test-session'}
        preview = self.request('/api/preview', {'text':LINE}, headers)
        self.assertEqual(preview['counts']['valid'],1)
        self.assertNotIn(PASSWORD, json.dumps(preview))
        self.assertEqual(self.request('/api/import', {'text':LINE}, headers)['imported'],1)
        account = self.request('/api/accounts')['items'][0]
        self.assertEqual(self.request('/api/reveal', {'id':account['id']}, headers)['token'],TOKEN)

    def test_cross_origin_and_missing_token_blocked(self):
        for headers in ({}, {'X-Session-Token':'test-session','Origin':'https://untrusted.example'}, {'X-Session-Token':'test-session','Host':'untrusted.example'}):
            with self.assertRaises(HTTPError) as error:
                self.request('/api/import', {'text':LINE}, headers)
            self.assertEqual(error.exception.code,403)
        self.assertEqual(self.store.accounts()['total'],0)

    def test_metadata_update_api(self):
        self.store.import_text(LINE, 'test')
        account_id = self.store.accounts()['items'][0]['id']
        headers = {'X-Session-Token':'test-session'}
        self.request('/api/account/update', {'id':account_id,'status':'banned','owner':'3090'}, headers)
        result = self.request('/api/accounts?status=banned&owner=3090&q=demo')
        self.assertEqual(result['matched'],1)
        self.assertEqual(result['items'][0]['owner'],'3090')
        for body in ({'id':account_id,'owner':'4090'}, {'id':account_id,'status':'bad'}):
            with self.assertRaises(HTTPError) as error: self.request('/api/account/update', body, headers)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error:
            self.request('/api/account/update', {'id':account_id,'status':'alive'})
        self.assertEqual(error.exception.code,403)

    def test_sorting_bulk_api_and_auth(self):
        self.store.import_text(LINE + '\n' + LINE.replace('demo@','other@'), 'test')
        headers = {'X-Session-Token':'test-session'}
        ids = self.request('/api/accounts/ids')['ids']
        self.assertEqual(ids, [1,2])
        self.assertEqual(self.request('/api/accounts?order=desc')['items'][0]['id'], 2)
        result = self.request('/api/accounts/bulk-update', {'ids':ids,'values':{'status':'banned','owner':'3080'}}, headers)
        self.assertEqual(result['updated'], 2)
        self.assertEqual(self.request('/api/accounts/ids?status=banned&owner=3080')['ids'], ids)
        for body in ({'ids':[],'values':{'status':'alive'}}, {'ids':ids,'values':{'owner':'4090'}}):
            with self.assertRaises(HTTPError) as error: self.request('/api/accounts/bulk-update', body, headers)
            self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error: self.request('/api/accounts/bulk-update', {'ids':ids,'values':{'status':'alive'}})
        self.assertEqual(error.exception.code,403)
        self.assertEqual(self.store.accounts(status='banned')['matched'],2)

    def test_serves_only_built_frontend(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'dist' / 'assets').mkdir(parents=True)
            (root / 'dist' / 'index.html').write_text('<h1>Built frontend</h1>')
            (root / 'dist' / 'assets' / 'index.js').write_text('export {};')
            (root / 'secret.py').write_text('private')
            with patch('app.ROOT', root):
                with urlopen(self.url + '/') as response:
                    self.assertIn(b'Built frontend', response.read())
                with urlopen(self.url + '/assets/index.js') as response:
                    self.assertTrue(response.headers['Content-Type'].startswith('text/javascript'))
                for path in ('/../secret.py', '/%2e%2e/secret.py', '/data/mailboxes.sqlite3', '/app.py'):
                    with self.assertRaises(HTTPError) as error: urlopen(self.url + path)
                    self.assertEqual(error.exception.code,404)

    def test_invalid_body(self):
        with self.assertRaises(HTTPError) as error:
            self.request('/api/preview', {'text':None}, {'X-Session-Token':'test-session'})
        self.assertEqual(error.exception.code,400)


if __name__ == '__main__':
    unittest.main()
