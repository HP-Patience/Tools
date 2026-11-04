#!/usr/bin/env bash
# One-time administrator setup for the user-approved IP and port.
# Run from the uploaded bundle. No package installs, firewall changes or existing-site edits.
set -euo pipefail
[[ "$EUID" == 0 ]] || { echo "Run using sudo bash setup-nginx-ip.sh"; exit 1; }
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
for command in nginx openssl python3 install useradd systemctl ss; do command -v "$command" >/dev/null; done
nginx -t
for target in /srv/zhixu /opt/zhixu /etc/nginx/zhixu.htpasswd /etc/nginx/sites-available/zhixu-ip /etc/nginx/sites-enabled/zhixu-ip; do
    [[ ! -e "$target" && ! -L "$target" ]] || { echo "STOP: already exists: $target (do not delete; ask for review)"; exit 1; }
done
if id zhixu-deploy >/dev/null 2>&1; then echo "STOP: zhixu-deploy already exists; review its permissions first."; exit 1; fi
if [[ -n "$(ss -H -ltn 'sport = :18443')" ]]; then echo "STOP: TCP 18443 is already listening."; exit 1; fi
openssl x509 -in /etc/letsencrypt/live/ai-prompt-optimizer-ip/fullchain.pem -noout -checkend 86400
openssl x509 -in /etc/letsencrypt/live/ai-prompt-optimizer-ip/fullchain.pem -noout -checkip 121.41.92.58
[[ -r /etc/letsencrypt/live/ai-prompt-optimizer-ip/privkey.pem ]]
[[ -f /etc/letsencrypt/renewal-hooks/deploy/ai-prompt-optimizer-nginx ]]

# Copy the bundle into root-owned scratch before validation and installation.
STAGE="$(mktemp -d /var/tmp/zhixu-setup.XXXXXXXX)"
cleanup() { rm -rf -- "$STAGE"; }
trap cleanup EXIT
cp -- "$SOURCE/activate.py" "$SOURCE/nginx-ip.conf" "$STAGE/"
cp -R -- "$SOURCE/release" "$STAGE/release"
VERSION="$(python3 "$STAGE/activate.py" verify "$STAGE/release")"
echo "Verified release: $VERSION"
echo "Website username: zhixu. Set a unique password of at least 12 characters."
IFS= read -r -s -p 'Website password: ' PASSWORD </dev/tty; echo
IFS= read -r -s -p 'Repeat password: ' REPEAT </dev/tty; echo
[[ ${#PASSWORD} -ge 12 && "$PASSWORD" == "$REPEAT" ]] || { echo "Passwords must match and contain at least 12 characters. Nothing installed."; exit 1; }
HASH="$(printf '%s\n' "$PASSWORD" | openssl passwd -6 -stdin)"
unset PASSWORD REPEAT
umask 077
printf 'zhixu:%s\n' "$HASH" > "$STAGE/htpasswd"
unset HASH

# Dedicated CI account: no sudo or docker membership, password login locked by default.
useradd --create-home --shell /bin/bash zhixu-deploy
install -d -o zhixu-deploy -g www-data -m 755 /srv/zhixu /srv/zhixu/releases
install -d -o zhixu-deploy -g www-data -m 700 /srv/zhixu/incoming
install -d -o root -g root -m 755 /opt/zhixu
install -o root -g root -m 755 "$STAGE/activate.py" /opt/zhixu/activate.py
cp -R -- "$STAGE/release" "/srv/zhixu/releases/$VERSION"
chown -R zhixu-deploy:www-data "/srv/zhixu/releases/$VERSION"
find "/srv/zhixu/releases/$VERSION" -type d -exec chmod 755 {} +
find "/srv/zhixu/releases/$VERSION" -type f -exec chmod 644 {} +
# Bootstrap without consuming a GitHub workflow run number.
ln -s "releases/$VERSION" /srv/zhixu/current
chown -h zhixu-deploy:www-data /srv/zhixu/current
install -o root -g www-data -m 640 "$STAGE/htpasswd" /etc/nginx/zhixu.htpasswd
install -o root -g root -m 644 "$STAGE/nginx-ip.conf" /etc/nginx/sites-available/zhixu-ip
ln -s /etc/nginx/sites-available/zhixu-ip /etc/nginx/sites-enabled/zhixu-ip
if ! nginx -t; then
    unlink /etc/nginx/sites-enabled/zhixu-ip
    echo "New site disabled after configuration test failed. Existing running sites were not reloaded."
    exit 1
fi
systemctl reload nginx
printf '\nREADY: https://121.41.92.58:18443\nUsername: zhixu\n'
echo "GitHub deployment SSH keys and Secrets are NOT configured yet."
