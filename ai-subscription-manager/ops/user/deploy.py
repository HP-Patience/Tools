"""Rootless deployment. Persistent data lives outside immutable releases."""

import fcntl, json, os, re, shlex, signal, subprocess, sys, tarfile, time, urllib.request
from pathlib import Path

os.umask(0o077)
root = Path.home() / "apps/ai-subscriptions"
sha = sys.argv[1]
archive = Path(sys.argv[2]).resolve()
if (
    not re.fullmatch(r"[0-9a-f]{40}", sha)
    or archive != root / "incoming" / f"{sha}.tar.gz"
):
    raise RuntimeError("Invalid deployment target")
lock = (root / "run/maintenance.lock").open("a")
fcntl.flock(lock, fcntl.LOCK_EX)
release = root / "releases" / sha
if (root / "current").is_symlink() and (root / "current").resolve() == release:
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:18080/health/", timeout=5
        ) as response:
            health = json.load(response)
        if health.get("release") == sha and health.get("status") == "ok":
            print("Same healthy release, no changes")
            sys.exit(0)
    except (OSError, ValueError):
        pass
release.mkdir(parents=True, exist_ok=True)
with tarfile.open(archive, "r:gz") as bundle:
    bundle.extractall(release, filter="data")
uv = root / "tools/uv"
python = release / ".venv/bin/python"
if not python.exists():
    subprocess.run(
        [str(uv), "venv", "--python", "/usr/bin/python3", str(release / ".venv")],
        check=True,
    )
subprocess.run(
    [
        str(uv),
        "pip",
        "install",
        "--python",
        str(python),
        "-r",
        str(release / "backend/requirements.lock"),
    ],
    check=True,
)
configuration = root / "shared/app.env"
if not configuration.exists():
    configuration.write_text(
        "APP_DATABASE_PATH="
        + str(root / "shared/subscriptions.db")
        + "\nAPP_APP_URL=http://localhost:18080\nAPP_PRODUCTION=false\nAPP_FRONTEND_DIR="
        + str(root / "current/frontend/dist")
        + "\nAPP_MAIL_BACKEND=disabled\n"
    )
    configuration.chmod(0o600)
env = os.environ.copy()
for line in configuration.read_text().splitlines():
    if not line or line.lstrip().startswith("#"):
        continue
    key, value = line.split("=", 1)
    parsed = shlex.split(value)
    env[key] = parsed[0] if parsed else ""
env["APP_RELEASE_SHA"] = sha
pid_file = root / "run/supervisor.pid"
if pid_file.exists():
    pid = int(pid_file.read_text())
    proc = Path("/proc") / str(pid)
    if proc.exists():
        command = (proc / "cmdline").read_bytes()
        if str(root / "bin/supervise.sh").encode() not in command:
            raise RuntimeError("Supervisor PID no longer belongs to this application")
        os.kill(pid, signal.SIGTERM)
        for _ in range(80):
            if not proc.exists():
                break
            time.sleep(0.2)
        else:
            raise RuntimeError("Supervisor did not stop; refusing migration")
if Path(env["APP_DATABASE_PATH"]).exists():
    subprocess.run(
        [
            str(python),
            str(release / "ops/backup.py"),
            env["APP_DATABASE_PATH"],
            str(root / "shared/backups"),
        ],
        check=True,
    )
subprocess.run(
    [str(python), "-m", "alembic", "upgrade", "head"],
    cwd=release / "backend",
    env=env,
    check=True,
)
for name in ["supervise.sh", "task.sh", "gateway.py", "deploy.py"]:
    target = root / "bin" / name
    target.write_bytes(
        (release / "ops/user" / name).read_bytes().replace(b"\r\n", b"\n")
    )
    target.chmod(0o700)
(release / "release.env").write_text("APP_RELEASE_SHA=" + sha + "\n")
temporary = root / "current.next"
if temporary.is_symlink():
    temporary.unlink()
elif temporary.exists():
    raise RuntimeError("Unexpected current.next path")
temporary.symlink_to(release, target_is_directory=True)
os.replace(temporary, root / "current")
with (root / "logs/service.log").open("ab") as logfile:
    subprocess.Popen(
        ["/bin/bash", str(root / "bin/supervise.sh")],
        stdin=subprocess.DEVNULL,
        stdout=logfile,
        stderr=logfile,
        start_new_session=True,
        close_fds=True,
    )
for _ in range(60):
    try:
        with urllib.request.urlopen(
            "http://127.0.0.1:18080/health/", timeout=2
        ) as response:
            health = json.load(response)
        if health.get("release") == sha and health.get("status") == "ok":
            break
    except Exception:
        pass
    time.sleep(0.5)
else:
    raise RuntimeError("Health check failed; inspect logs/service.log")
previous = subprocess.run(["crontab", "-l"], text=True, capture_output=True)
if previous.returncode not in (0, 1) or "not allowed" in previous.stderr.lower():
    raise RuntimeError("User crontab unavailable")
lines = [
    line
    for line in previous.stdout.splitlines()
    if "# ai-subscriptions-managed" not in line
]
service = f"/bin/bash {root}/bin/supervise.sh >>{root}/logs/service.log 2>&1 # ai-subscriptions-managed"
lines += [
    "@reboot " + service,
    "* * * * * " + service,
    f"*/15 * * * * /bin/bash {root}/bin/task.sh reminders >>{root}/logs/tasks.log 2>&1 # ai-subscriptions-managed",
    f"0 3 * * * /bin/bash {root}/bin/task.sh backup >>{root}/logs/tasks.log 2>&1 # ai-subscriptions-managed",
]
subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n", text=True, check=True)
print(
    "Healthy release " + sha + "; user startup, reminders and backup scheduled",
    flush=True,
)
