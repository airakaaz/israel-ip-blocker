#!/usr/bin/env python3
"""Refresh nftables sets containing IP allocations registered to Israel."""

import ipaddress
import shutil
import subprocess
import sys
import tempfile
import urllib.request

NFT = shutil.which("nft") or "/usr/sbin/nft"
TABLE = "block_israel"
FEEDS = (
    "https://ftp.afrinic.net/pub/stats/afrinic/delegated-afrinic-latest",
    "https://ftp.apnic.net/stats/apnic/delegated-apnic-latest",
    "https://ftp.arin.net/pub/stats/arin/delegated-arin-extended-latest",
    "https://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest",
    "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest",
)


def fetch(url):
    print(f"fetching {url}", file=sys.stderr, flush=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "systemd-block-israel/1.0"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
        print(f"fetched {len(body)} bytes from {url}", file=sys.stderr, flush=True)
        return body.decode("utf-8", errors="replace")


def to_cidrs(start, count):
    first = ipaddress.ip_address(start)
    last = ipaddress.ip_address(int(first) + count - 1)
    return ipaddress.summarize_address_range(first, last)


def collect():
    v4, v6 = set(), set()

    for url in FEEDS:
        before_v4, before_v6 = len(v4), len(v6)
        for line in fetch(url).splitlines():
            if not line or line.startswith("#"):
                continue

            fields = line.split("|")
            if len(fields) < 7:
                continue

            _, country, kind, start, value, _date, status, *_ = fields

            if country.upper() != "IL":
                continue
            if kind not in {"ipv4", "ipv6"}:
                continue
            if status.lower() not in {"allocated", "assigned"}:
                continue

            target = v4 if kind == "ipv4" else v6
            target.update(str(network) for network in to_cidrs(start, int(value)))

        print(
            f"feed contributed {len(v4) - before_v4} IPv4 and "
            f"{len(v6) - before_v6} IPv6 prefixes: {url}",
            file=sys.stderr,
            flush=True,
        )

    if not v4 and not v6:
        raise RuntimeError("all feeds returned zero Israeli ranges")

    return (
        sorted(v4, key=ipaddress.ip_network),
        sorted(v6, key=ipaddress.ip_network),
    )


def run_nft(lines):
    print(f"running nft batch with {len(lines)} statements", file=sys.stderr, flush=True)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".nft") as handle:
        handle.write("\n".join(lines) + "\n")
        handle.flush()
        result = subprocess.run(
            [NFT, "-f", handle.name],
            text=True,
            capture_output=True,
        )
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
    try:
        v4, v6 = collect()
        print(f"collected {len(v4)} IPv4 and {len(v6)} IPv6 prefixes", file=sys.stderr, flush=True)
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
