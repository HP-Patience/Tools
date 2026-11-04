"""Run a real Caddy against an isolated release copy, then optional production browser tests.
Usage: python tests/security/caddy_smoke.py --caddy work/caddy.exe --browser
The local HTTP address is for the smoke test only; production uses the original HTTPS config.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument('--caddy', required=True, type=Path)
parser.add_argument('--browser', action='store_true')
args = parser.parse_args()
caddy = str(args.caddy.resolve(strict=True))
root = Path(__file__).resolve().parents[2]
release = root / 'release'
manifest = json.loads((release / 'manifest.json').read_text())
with socket.socket() as probe:
    probe.bind(('127.0.0.1', 0))
    port = probe.getsockname()[1]
base = f'http://127.0.0.1:{port}'
user, password = 'smoke-user', secrets.token_urlsafe(28)
hash_value = subprocess.check_output([caddy, 'hash-password', '--plaintext', password], text=True).strip()
env = {**os.environ, 'ATLAS_DOMAIN': base, 'ATLAS_USER': user, 'ATLAS_PASSWORD_HASH': hash_value}
flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
with tempfile.TemporaryDirectory(prefix='zhixu-caddy-') as directory:
    temp = Path(directory)
    versions = temp / 'releases'
    shutil.copytree(release, versions / manifest['version'])
    shutil.copytree(release, versions / 'old-protected-version')
    shutil.copytree(release, temp / 'current')
    config = (root / 'deploy/Caddyfile').read_text()
    # Validate the unmodified production template first (without starting public listeners).
    prod_env = {**env, 'ATLAS_DOMAIN': 'map.example.test'}
    subprocess.run([caddy, 'validate', '--config', str(root / 'deploy/Caddyfile'), '--adapter', 'caddyfile'], env=prod_env, check=True, capture_output=True)
    config = '{\n admin off\n auto_https off\n}\n' + config
    config = config.replace('/srv/zhixu/releases', '"' + versions.as_posix() + '"').replace('/srv/zhixu/current', '"' + (temp / 'current').as_posix() + '"')
    config_file = temp / 'Caddyfile'
    config_file.write_text(config)
    subprocess.run([caddy, 'validate', '--config', str(config_file), '--adapter', 'caddyfile'], env=env, check=True, capture_output=True)
    with (temp / 'caddy.log').open('wb') as log:
        process = subprocess.Popen([caddy, 'run', '--config', str(config_file), '--adapter', 'caddyfile'], env=env, stdout=log, stderr=log, creationflags=flags)
        try:
            def request(path, credentials=None):
                headers = {}
                if credentials:
                    headers['Authorization'] = 'Basic ' + base64.b64encode(credentials.encode()).decode()
                try:
                    with urllib.request.urlopen(urllib.request.Request(base + path, headers=headers), timeout=3) as response:
                        return response.status, response.read(), response.headers
                except urllib.error.HTTPError as error:
                    return error.code, error.read(), error.headers

            for _ in range(80):
                if process.poll() is not None:
                    raise RuntimeError('Caddy exited before smoke test')
                try:
                    if request('/')[0] == 401:
                        break
                except urllib.error.URLError:
                    pass
                time.sleep(.1)
            else:
                raise TimeoutError('Caddy did not start')
            checked = 0
            for name in manifest['files']:
                url = f"/versions/{manifest['version']}/{name}"
                assert request(url)[0] == 401, url
                assert request(url, user + ':wrong')[0] == 401, url
                status, body, headers = request(url, user + ':' + password)
                assert status == 200 and body == (release / name).read_bytes(), url
                assert 'no-store' in headers['Cache-Control']
                assert "frame-ancestors 'none'" in headers['Content-Security-Policy']
                assert request('/versions/old-protected-version/' + name)[0] == 401
                checked += 4
            assert request('/')[0] == 401
            assert request('/', user + ':wrong')[0] == 401
            assert request('/', user + ':' + password)[0] == 200
            for path in ['/.git/config', '/AGENTS.md', '/.local/backups', '/__atlas/map']:
                assert request(path)[0] == 401
                assert request(path, user + ':' + password)[0] == 404
                checked += 2
            print(f'Caddy production config valid; {checked + 3} HTTP authentication/content checks passed.', flush=True)
            if args.browser:
                browser_env = {**os.environ, 'ATLAS_SMOKE_URL': base, 'ATLAS_SMOKE_USER': user, 'ATLAS_SMOKE_PASSWORD': password}
                subprocess.run(['node', 'tests/security/production-browser.mjs'], cwd=root, env=browser_env, check=True)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
