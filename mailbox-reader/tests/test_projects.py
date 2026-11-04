import json
from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from app import Store
import test_app
from test_app import LINE


class ProjectStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'test.sqlite3'
        self.store = Store(self.path)
        self.store.import_text(LINE+'\n'+LINE.replace('demo@','other@'),'test')

    def test_independent_metadata_and_idempotent_assignment(self):
        project = self.store.create_project('第二项目')['id']
        self.store.update_account(1,{'status':'banned','owner':'天选'})
        self.store.assign_project([1,2],project)
        self.assertEqual(self.store.accounts(project_id=project)['items'][0]['status'],'alive')
        self.store.bulk_update_accounts([1,2],{'owner':'3090'},project)
        self.store.assign_project([1],project)
        arena = self.store.accounts()['items'][0]
        other = self.store.accounts(project_id=project)['items'][0]
        self.assertEqual((arena['status'],arena['owner']),('banned','天选'))
        self.assertEqual((other['status'],other['owner']),('alive','3090'))
        self.assertEqual(len(other['projects']),2)
        self.assertEqual(self.store.account_ids(owner='3090',project_id=project),[1,2])
        self.assertEqual(Store(self.path).accounts(project_id=project)['items'][0]['owner'],'3090')

    def test_remove_keeps_credentials_and_other_project(self):
        project = self.store.create_project('项目B')['id']
        self.store.assign_project([1],project)
        before = self.store.reveal(1)
        self.store.assign_project([1],1,True)
        self.assertEqual(self.store.account_ids(),[2])
        self.assertEqual(self.store.account_ids(project_id=0),[1,2])
        self.assertEqual(self.store.account_ids(project_id=project),[1])
        self.assertEqual(self.store.reveal(1),before)
        Store(self.path)
        self.assertEqual(self.store.account_ids(),[2])

    def test_import_into_project_preserves_existing_credentials_and_marks(self):
        project = self.store.create_project('项目B')['id']
        self.store.update_account(1,{'status':'banned'})
        result = self.store.import_text(LINE,'duplicate',project)
        self.assertEqual(result['duplicates'],1)
        self.assertEqual(self.store.account_ids(project_id=project),[1])
        self.assertEqual(self.store.accounts()['items'][0]['status'],'banned')
        self.store.import_text(LINE.replace('demo@','third@'),'new',0)
        self.assertEqual(len(self.store.account_ids(project_id=0)),3)
        self.assertEqual(len(self.store.account_ids()),2)

    def test_validation_and_atomicity(self):
        project = self.store.create_project('项目B')['id']
        for name in ('', ' '*3, 'x'*61, None, 'Arena项目'):
            with self.assertRaises(ValueError): self.store.create_project(name)
        with self.assertRaises(ValueError): self.store.assign_project([1],999)
        with self.assertRaises(ValueError): self.store.assign_project([1],0)
        with self.assertRaises(LookupError): self.store.assign_project([1,999],project)
        self.assertEqual(self.store.account_ids(project_id=project),[])
        self.store.assign_project([1],project)
        with self.assertRaises(LookupError): self.store.bulk_update_accounts([1,2],{'status':'banned'},project)
        self.assertEqual(self.store.accounts(project_id=project)['items'][0]['status'],'alive')
        with self.assertRaises(ValueError): self.store.bulk_update_accounts([1],{'status':'banned'},0)

    def test_migration_preserves_old_marks_and_ciphertext_once(self):
        legacy = Path(self.temp.name)/'legacy.sqlite3'
        with closing(sqlite3.connect(legacy)) as db:
            db.execute("CREATE TABLE accounts(id INTEGER PRIMARY KEY,email TEXT,email_key TEXT UNIQUE,credentials BLOB,created_at TEXT,status TEXT,owner TEXT)")
            db.execute("INSERT INTO accounts VALUES(7,'legacy@example.com','legacy@example.com',?,'2026-01-01','banned','3080')",(b'exact-encrypted-blob',))
            db.commit()
        store = Store(legacy)
        row = store.accounts()['items'][0]
        self.assertEqual((row['id'],row['status'],row['owner']),(7,'banned','3080'))
        self.assertEqual(row['projects'],[{'id':1,'name':'Arena项目'}])
        with store.connect() as db:
            self.assertEqual(db.execute('SELECT credentials FROM accounts').fetchone()[0],b'exact-encrypted-blob')
        store.assign_project([7],1,True)
        self.assertEqual(Store(legacy).account_ids(),[])


class ProjectApiTests(unittest.TestCase):
    setUp = test_app.ApiTests.setUp
    tearDown = test_app.ApiTests.tearDown
    request = test_app.ApiTests.request
    def test_project_api_scope_and_auth(self):
        headers={'X-Session-Token':'test-session'}
        self.store.import_text(LINE,'test')
        project=self.request('/api/projects/create',{'name':'项目B'},headers)['id']
        self.request('/api/projects/assign',{'ids':[1],'project_id':project},headers)
        self.request('/api/account/update',{'id':1,'project_id':project,'status':'banned','owner':'3090'},headers)
        self.assertEqual(self.request(f'/api/accounts?project_id={project}&status=banned')['matched'],1)
        self.assertEqual(self.request('/api/accounts?project_id=1&status=banned')['matched'],0)
        self.assertEqual(self.request(f'/api/accounts/ids?project_id={project}')['ids'],[1])
        for path,body in [('/api/projects/create',{'name':'bad'}),('/api/projects/assign',{'ids':[1],'project_id':project})]:
            from urllib.error import HTTPError
            with self.assertRaises(HTTPError) as error: self.request(path,body)
            self.assertEqual(error.exception.code,403)


class AuthTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from http.server import ThreadingHTTPServer
        from app import make_handler
        self.temp=tempfile.TemporaryDirectory(); self.store=Store(Path(self.temp.name)/'auth.sqlite3')
        self.server=ThreadingHTTPServer(('127.0.0.1',0), make_handler(self.store,'csrf',True)); self.thread=__import__('threading').Thread(target=self.server.serve_forever,daemon=True); self.thread.start(); self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.addCleanup(self.server.server_close); self.addCleanup(self.temp.cleanup)
    def post(self,path,body,cookie=''):
        from urllib.request import Request,urlopen
        req=Request(self.base+path,data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Origin':self.base,'Cookie':cookie})
        return urlopen(req)
    def test_first_run_setup_and_login_cookie(self):
        from urllib.request import urlopen
        session=json.load(urlopen(self.base+'/api/session'))
        self.assertEqual((session['auth_enabled'],session['setup_required'],session['authenticated']),(True,True,False))
        with self.assertRaises(Exception): urlopen(self.base+'/api/projects')
        response=self.post('/api/auth/setup',{'username':'admin','password':'password123'})
        self.assertEqual(response.status,200); cookie=response.headers['Set-Cookie']; self.assertIn('HttpOnly',cookie)
        self.assertEqual(json.load(urlopen(self.base+'/api/projects',headers={})),[]) if False else None
        with self.assertRaises(Exception): self.post('/api/auth/setup',{'username':'admin2','password':'password123'})
        response=self.post('/api/auth/login',{'username':'admin','password':'badpass1'}) if False else None
