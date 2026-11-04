"""Double-click entry point. Reuse an existing instance, start one if needed."""
from pathlib import Path
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
import tkinter as tk
from tkinter import messagebox

BASE = Path(__file__).resolve().parent
URL = 'http://127.0.0.1:8767'

def healthy():
    try:
        with urllib.request.urlopen(URL + '/api/health', timeout=1) as response:
            return json.load(response).get('app') == 'penrose-atrium'
    except (OSError, ValueError):
        return False

def main():
    if not healthy():
        python = BASE / '.venv' / 'Scripts' / 'pythonw.exe'
        if not python.exists():
            raise RuntimeError('找不到项目 Python 环境，请检查 .venv 文件夹是否完整。')
        with (BASE / 'web' / 'server-error.log').open('a', encoding='utf-8') as log:
            proc = subprocess.Popen([str(python), str(BASE / 'web' / 'server.py')],
                                    cwd=BASE / 'web', stdout=log, stderr=log)
        for _ in range(50):
            if healthy():
                break
            if proc.poll() is not None:
                raise RuntimeError('本地服务启动失败，8767 端口可能被其他程序占用。\n详见 web\\server-error.log。')
            time.sleep(.2)
        else:
            proc.terminate()
            raise RuntimeError('本地服务启动超时，请重试。')
    webbrowser.open(URL)

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        root=tk.Tk();root.withdraw()
        messagebox.showerror('回环 · 启动失败', str(exc), parent=root)
        root.destroy()
