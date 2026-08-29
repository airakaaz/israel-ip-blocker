#!/usr/bin/env bash
set -Eeuo pipefail

PERMANENT=false
case "${1:-}" in
    "") ;;
    --permanent) PERMANENT=true ;;
    *) printf 'usage: %s [--permanent]\n' "$0" >&2; exit 2 ;;
esac

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SYSTEMD_DIR="/etc/systemd/system"
LIBEXEC_DIR="/usr/local/libexec"
SERVICE_NAME="block-israel.service"
TIMER_NAME="block-israel.timer"
UPDATER_NAME="update-block-israel.py"
FETCHER_NAME="fetch_il_ip_ranges.py"

if [[ "${EUID}" -ne 0 ]]; then
    exec sudo -- "$0" "$@"
fi

for command in install ln systemctl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        printf 'error: required command not found: %s\n' "$command" >&2
        exit 1
    fi
done

for file in "$SOURCE_DIR/$SERVICE_NAME" "$SOURCE_DIR/$TIMER_NAME" "$SOURCE_DIR/$UPDATER_NAME" "$SOURCE_DIR/$FETCHER_NAME"; do
    if [[ ! -f "$file" ]]; then
        printf 'error: missing source file: %s\n' "$file" >&2
        exit 1
    fi
done

if [[ ! -x /usr/bin/python3 ]]; then
    printf 'error: /usr/bin/python3 is required on this host\n' >&2
    exit 1
fi

if ! command -v nft >/dev/null 2>&1; then
    printf 'error: nftables is not installed or nft is not in PATH\n' >&2
    exit 1
fi

install -d -m 0755 "$LIBEXEC_DIR"

if "$PERMANENT"; then
    install -m 0755 "$SOURCE_DIR/$FETCHER_NAME" \
        "$LIBEXEC_DIR/$FETCHER_NAME"
    install -m 0755 "$SOURCE_DIR/$UPDATER_NAME" \
        "$LIBEXEC_DIR/$UPDATER_NAME"
    install -m 0644 "$SOURCE_DIR/$SERVICE_NAME" \
        "$SYSTEMD_DIR/$SERVICE_NAME"
    install -m 0644 "$SOURCE_DIR/$TIMER_NAME" \
        "$SYSTEMD_DIR/$TIMER_NAME"
else
    ln -sfn "$SOURCE_DIR/$FETCHER_NAME" \
        "$LIBEXEC_DIR/$FETCHER_NAME"
    ln -sfn "$SOURCE_DIR/$UPDATER_NAME" \
        "$LIBEXEC_DIR/$UPDATER_NAME"
    ln -sfn "$SOURCE_DIR/$SERVICE_NAME" \
        "$SYSTEMD_DIR/$SERVICE_NAME"
    ln -sfn "$SOURCE_DIR/$TIMER_NAME" \
        "$SYSTEMD_DIR/$TIMER_NAME"
fi

systemctl daemon-reload
systemctl enable --now "$TIMER_NAME"
systemctl start "$SERVICE_NAME"

if "$PERMANENT"; then
    printf 'Installed permanent copies and activated %s.\n' "$TIMER_NAME"
else
    printf 'Installed symlinks and activated %s.\n' "$TIMER_NAME"
fi
systemctl --no-pager --full status "$TIMER_NAME"
