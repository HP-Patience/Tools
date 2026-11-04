#!/usr/bin/env bash
# Install only the dedicated public key, retaining any existing authorized keys.
set -euo pipefail
[[ "$EUID" == 0 ]] || { echo "Run this script with sudo bash."; exit 1; }
SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
USER_NAME=zhixu-deploy
HOME_DIR=/home/zhixu-deploy
[[ "$(getent passwd "$USER_NAME" | cut -d: -f6)" == "$HOME_DIR" ]] || { echo "Unexpected deployment account home."; exit 1; }
[[ -d "$HOME_DIR" && ! -L "$HOME_DIR" ]] || exit 1
for target in "$HOME_DIR/.ssh" "$HOME_DIR/.ssh/authorized_keys"; do
    [[ ! -L "$target" ]] || { echo "Refusing symlink: $target"; exit 1; }
done
# Public key only. Nothing in this bundle contains the private CI credential.
LINE="$(cat "$SOURCE/authorized-key.pub")"
[[ "$LINE" =~ ^restrict\ ssh-ed25519\ [A-Za-z0-9+/=]+\ knowledge-map-github-actions$ ]] || { echo "Unexpected public key format."; exit 1; }
ssh-keygen -l -f "$SOURCE/authorized-key.pub"
install -d -o "$USER_NAME" -g "$USER_NAME" -m 700 "$HOME_DIR/.ssh"
KEYS="$HOME_DIR/.ssh/authorized_keys"
if [[ -e "$KEYS" && ! -f "$KEYS" ]]; then echo "Unexpected authorized_keys file type."; exit 1; fi
if [[ ! -f "$KEYS" ]]; then
    install -o "$USER_NAME" -g "$USER_NAME" -m 600 /dev/null "$KEYS"
fi
if ! grep -qxF -- "$LINE" "$KEYS"; then
    # Separate from any preexisting unterminated final line; never overwrite existing keys.
    printf '\n%s\n' "$LINE" >> "$KEYS"
fi
chown "$USER_NAME:$USER_NAME" "$KEYS"
chmod 600 "$KEYS"
echo "READY: dedicated GitHub deployment public key installed."
echo "No changes to work SSH access, sudo, nginx, or the website password."
