#!/usr/bin/python3
"""An SSH deploy key may upload one release or activate it, never open a shell."""

import os, re, shlex, subprocess, sys
from pathlib import Path


def allowed_command(command, root):
    root = root.as_posix()
    parts = shlex.split(command)
    upload = re.compile(re.escape(root + "/incoming/") + r"[a-f0-9]{40}\.tar\.gz")
    if len(parts) == 3 and parts[:2] == ["scp", "-t"] and upload.fullmatch(parts[2]):
        return ["/usr/bin/scp", "-t", parts[2]]
    if (
        len(parts) == 4
        and parts[:2] == ["bash", root + "/deploy.sh"]
        and re.fullmatch(r"[a-f0-9]{40}", parts[2])
        and parts[3] == root + "/incoming/" + parts[2] + ".tar.gz"
    ):
        return ["/bin/bash", *parts[1:]]
    raise ValueError(
        "This key only permits upload and activation of application releases"
    )


def main():
    try:
        command = allowed_command(
            os.environ.get("SSH_ORIGINAL_COMMAND", ""),
            Path.home() / "apps/ai-subscriptions",
        )
    except ValueError:
        print("Command not permitted", file=sys.stderr)
        return 1
    return subprocess.call(command)


if __name__ == "__main__":
    sys.exit(main())
