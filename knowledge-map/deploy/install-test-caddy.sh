#!/usr/bin/env bash
# Isolated CI/test dependency only; does not install a system service.
set -euo pipefail
mkdir -p work
curl --fail --silent --show-error --location \
  https://github.com/caddyserver/caddy/releases/download/v2.11.4/caddy_2.11.4_linux_amd64.tar.gz \
  --output work/caddy-linux.tar.gz
printf '%s  %s\n' 8220d1f013b6f27510247b2360c9e0ca9f018feebd82515f07635318b34ff9777ccc8fd0b6e6f2486ce3a33fe389fbb7db12d05baa474f4587509fb4f5ebf1c9 work/caddy-linux.tar.gz | sha512sum --check
tar -xzf work/caddy-linux.tar.gz -C work caddy
work/caddy version
