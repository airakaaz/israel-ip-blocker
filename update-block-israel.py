#!/usr/bin/env python3
"""Refresh nftables sets using the shared RIR fetcher."""

import argparse
import ipaddress
import shutil
import subprocess
import sys
import tempfile

from fetch_il_ip_ranges import collect

NFT = shutil.which("nft") or "/usr/sbin/nft"
TABLE = "block_israel"


def run_nft(lines):
    print(f"running nft batch with {len(lines)} statements", file=sys.stderr, flush=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nft") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        result = subprocess.run([NFT, "-f", handle.name], text=True, capture_output=True)
        if result.stdout:
            print(f"nft stdout: {result.stdout.rstrip()}", file=sys.stderr, flush=True)
        if result.stderr:
            print(f"nft stderr: {result.stderr.rstrip()}", file=sys.stderr, flush=True)
        if result.returncode:
            print(f"nft exited with status {result.returncode}", file=sys.stderr, flush=True)
            raise subprocess.CalledProcessError(result.returncode, [NFT, "-f", handle.name])


def ensure_table():
    exists = subprocess.run(
        [NFT, "list", "table", "inet", TABLE],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0
    if exists:
        print(f"nftables table inet {TABLE} already exists", file=sys.stderr, flush=True)
        return

    print(f"creating nftables table inet {TABLE}", file=sys.stderr, flush=True)
    run_nft([
        f"add table inet {TABLE}",
        f"add set inet {TABLE} v4 {{ type ipv4_addr; flags interval; }}",
        f"add set inet {TABLE} v6 {{ type ipv6_addr; flags interval; }}",
        f"add chain inet {TABLE} input {{ type filter hook input priority -100; policy accept; }}",
        f"add chain inet {TABLE} output {{ type filter hook output priority -100; policy accept; }}",
        f"add chain inet {TABLE} forward {{ type filter hook forward priority -100; policy accept; }}",
        f"add rule inet {TABLE} input ip saddr @v4 drop",
        f"add rule inet {TABLE} input ip6 saddr @v6 drop",
        f"add rule inet {TABLE} output ip daddr @v4 drop",
        f"add rule inet {TABLE} output ip6 daddr @v6 drop",
        f"add rule inet {TABLE} forward ip saddr @v4 drop",
        f"add rule inet {TABLE} forward ip6 saddr @v6 drop",
        f"add rule inet {TABLE} forward ip daddr @v4 drop",
        f"add rule inet {TABLE} forward ip6 daddr @v6 drop",
    ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--managed-table",
        action="store_true",
        help="Expect NixOS to manage the table and only refresh its sets",
    )
    args = parser.parse_args()

    try:
        v4, v6, _records = collect()
        print(f"collected {len(v4)} IPv4 and {len(v6)} IPv6 prefixes", file=sys.stderr, flush=True)
        if args.managed_table:
            print(f"using declaratively managed nftables table inet {TABLE}", file=sys.stderr, flush=True)
        else:
            ensure_table()

        lines = [
            f"flush set inet {TABLE} v4",
            f"flush set inet {TABLE} v6",
        ]
        if v4:
            lines.append(f"add element inet {TABLE} v4 {{ " + ", ".join(v4) + " }")
        if v6:
            lines.append(f"add element inet {TABLE} v6 {{ " + ", ".join(v6) + " }")

        run_nft(lines)
        print(f"loaded {len(v4)} IPv4 and {len(v6)} IPv6 prefixes")
    except Exception as exc:
        print(f"block-israel update failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
