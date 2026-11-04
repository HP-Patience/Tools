#!/usr/bin/env python3
"""Verified, atomic static-site deployment. Server-side script; no third-party modules."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import sys

VERSION = re.compile(r"[0-9]{14}-[a-f0-9]{10}")
ASSET = re.compile(r"(?:index\.html|build-info\.json|assets/[A-Za-z0-9_.-]+\.(?:js|css|json|svg|png|woff|woff2|ttf))")


def verify(directory):
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("release must be a real directory")
    paths = list(directory.rglob('*'))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ValueError("symlinks and special files forbidden")
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schemaVersion') != 1 or not VERSION.fullmatch(manifest.get('version', '')):
        raise ValueError('invalid manifest version')
    for key in ('sourceHash', 'mapHash'):
        if not re.fullmatch(r'[a-f0-9]{64}', manifest.get(key, '')):
            raise ValueError('invalid fingerprint')
    actual = {p.relative_to(directory).as_posix() for p in paths if p.is_file()} - {'manifest.json'}
    files = manifest.get('files')
    if not isinstance(files, dict) or actual != set(files) or not {'index.html', 'build-info.json'} <= actual:
        raise ValueError('file inventory mismatch')
    for name in actual:
        if not ASSET.fullmatch(name):
            raise ValueError('file not allowed: ' + name)
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != files[name]:
            raise ValueError('hash mismatch: ' + name)
    info = json.loads((directory / 'build-info.json').read_text(encoding='utf-8'))
    if any(info.get(k) != manifest.get(k) for k in ('version', 'builtAt', 'sourceHash', 'mapHash')):
        raise ValueError('metadata mismatch')
    if f"/versions/{manifest['version']}/assets/" not in (directory / 'index.html').read_text(encoding='utf-8'):
        raise ValueError('versioned resource path mismatch')
    return manifest


def inside(root, path):
    resolved = path.resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise ValueError('path escapes deployment root')
    return resolved


@contextmanager
def lock(root):
    # Production target is Linux. Windows branch allows running integration tests locally.
    with (root / '.deploy.lock').open('a+b') as handle:
        if os.name == 'nt':
            import msvcrt
            handle.seek(0)
            handle.write(b'0')
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == 'nt':
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle, fcntl.LOCK_UN)


def switch(root, version):
    destination = inside(root, root / 'releases' / version)
    if destination.parent != root / 'releases':
        raise ValueError('invalid release location')
    current = root / 'current'
    if current.exists() or current.is_symlink():
        if not current.is_symlink():
            raise ValueError('current must be a symlink')
        old = inside(root, current)
        if old.parent != root / 'releases':
            raise ValueError('current target invalid')
        if old == destination:
            return
        temp_previous = root / '.previous-next'
        temp_previous.unlink(missing_ok=True)
        temp_previous.symlink_to(old, target_is_directory=True)
        os.replace(temp_previous, root / 'previous')
    temp = root / '.current-next'
    temp.unlink(missing_ok=True)
    temp.symlink_to(destination, target_is_directory=True)
    os.replace(temp, current)


def activate(root, token):
    if not re.fullmatch(r'[1-9][0-9]*-[1-9][0-9]*', token):
        raise ValueError('invalid run token')
    order = tuple(int(n) for n in token.split('-'))
    root = root.resolve(strict=True)
    with lock(root):
        incoming = inside(root, root / 'incoming' / token)
        if incoming != root / 'incoming' / token:
            raise ValueError('incoming cannot be a symlink')
        state_file = root / 'last-run.json'
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        if order <= tuple(state.get('order', [0, 0])):
            raise ValueError('stale or already activated workflow run')
        manifest = verify(incoming)
        releases = root / 'releases'
        releases.mkdir(exist_ok=True)
        if releases.is_symlink():
            raise ValueError('releases cannot be a symlink')
        destination = releases / manifest['version']
        if destination.exists():
            if verify(destination) != manifest:
                raise ValueError('version collision')
        else:
            os.replace(incoming, destination)
        # Restrictive SSH umask must not prevent Caddy reading public-to-authenticated-user assets.
        destination.chmod(0o755)
        for item in destination.rglob('*'):
            item.chmod(0o755 if item.is_dir() else 0o644)
        switch(root, manifest['version'])
        temp = root / '.last-run-next.json'
        temp.write_text(json.dumps({'order': order, 'version': manifest['version']}))
        os.replace(temp, state_file)
        return manifest['version']


def rollback(root, version):
    if not VERSION.fullmatch(version):
        raise ValueError('invalid rollback version')
    root = root.resolve(strict=True)
    with lock(root):
        directory = inside(root, root / 'releases' / version)
        if directory != root / 'releases' / version:
            raise ValueError('rollback release cannot be a symlink')
        if verify(directory)['version'] != version:
            raise ValueError('rollback metadata mismatch')
        switch(root, version)
        # Preserve last-run order, so delayed old workflows cannot undo the rollback.
        return version


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('/srv/zhixu'))
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('activate').add_argument('token')
    commands.add_parser('rollback').add_argument('version')
    commands.add_parser('verify').add_argument('directory', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'verify':
            print(verify(args.directory)['version'])
        elif args.command == 'activate':
            print(activate(args.root, args.token))
        else:
            print(rollback(args.root, args.version))
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        print('Deployment refused: ' + str(error), file=sys.stderr)
        sys.exit(1)
