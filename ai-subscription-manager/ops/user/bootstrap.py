"""Install one verified user-local tool; never changes system packages."""

import hashlib, io, json, os, shutil, tarfile, urllib.request
from pathlib import Path

os.umask(0o077)
root = Path.home() / "apps/ai-subscriptions"
for folder in ["tools", "bin", "run", "logs", "shared", "incoming", "releases"]:
    (root / folder).mkdir(parents=True, exist_ok=True)
(root / "shared").chmod(0o700)
uv = root / "tools/uv"
if not uv.exists():
    request = urllib.request.Request(
        "https://api.github.com/repos/astral-sh/uv/releases/latest",
        headers={"User-Agent": "subscription-desk-deployer"},
    )
    release = json.load(urllib.request.urlopen(request, timeout=30))
    name = "uv-x86_64-unknown-linux-gnu.tar.gz"
    asset = next(a for a in release["assets"] if a["name"] == name)
    data = urllib.request.urlopen(asset["browser_download_url"], timeout=90).read()
    expected = asset.get("digest", "")
    if expected and expected.startswith("sha256:"):
        expected = expected.split(":", 1)[1]
    else:
        checksum = next(a for a in release["assets"] if a["name"] == name + ".sha256")
        expected = (
            urllib.request.urlopen(checksum["browser_download_url"], timeout=30)
            .read()
            .decode()
            .split()[0]
        )
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("uv checksum mismatch")
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        member = next(
            m for m in archive.getmembers() if m.name.endswith("/uv") and m.isfile()
        )
        with archive.extractfile(member) as source, uv.open("wb") as target:
            shutil.copyfileobj(source, target)
    uv.chmod(0o700)
    print("Installed checksum-verified uv " + release["tag_name"], flush=True)
print("User deployment directories prepared", flush=True)
