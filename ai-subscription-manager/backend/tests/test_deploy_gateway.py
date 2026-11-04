import importlib.util
from pathlib import Path, PurePosixPath
import pytest


@pytest.fixture
def gateway():
    spec = importlib.util.spec_from_file_location(
        "gateway", Path(__file__).resolve().parents[2] / "ops/user/gateway.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gateway_only_allows_release_upload_and_activation(gateway):
    root = PurePosixPath("/home/work/apps/ai-subscriptions")
    sha = "a" * 40
    incoming = str(root / "incoming" / f"{sha}.tar.gz")
    assert gateway.allowed_command("scp -t " + incoming, root) == ["/usr/bin/scp", "-t", incoming]
    assert gateway.allowed_command(f"bash {root}/deploy.sh '{sha}' '{incoming}'", root) == [
        "/bin/bash",
        str(root / "deploy.sh"),
        sha,
        incoming,
    ]


@pytest.mark.parametrize(
    "command",
    [
        "bash -c whoami",
        "cat /etc/passwd",
        "scp -t /tmp/file",
        "scp -t /home/work/apps/ai-subscriptions/incoming/../../file",
        "internal-sftp",
        "scp -r -t /tmp/file",
    ],
)
def test_gateway_rejects_other_commands(gateway, command):
    with pytest.raises(ValueError):
        gateway.allowed_command(command, PurePosixPath("/home/work/apps/ai-subscriptions"))


@pytest.mark.parametrize("name", ["supervise.sh", "task.sh"])
def test_user_service_shell_syntax(name):
    import os, shutil, subprocess

    git = Path(shutil.which("git"))
    bash = str(git.parent.parent / "bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    path = Path(__file__).resolve().parents[2] / "ops/user" / name
    assert b"\r" not in path.read_bytes(), "Linux service scripts must use LF line endings"
    result = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
