#!/usr/bin/env python3
"""Fetch IP allocations registered to Israel (IL) from all five RIRs."""

from __future__ import annotations

import argparse
import csv
import ipaddress
import json
import sys
import urllib.error
import urllib.request
from typing import Any

RIR_FEEDS = {
    "afrinic": "https://ftp.afrinic.net/pub/stats/afrinic/delegated-afrinic-latest",
    "apnic": "https://ftp.apnic.net/stats/apnic/delegated-apnic-latest",
    "arin": "https://ftp.arin.net/pub/stats/arin/delegated-arin-extended-latest",
    "lacnic": "https://ftp.lacnic.net/pub/stats/lacnic/delegated-lacnic-latest",
    "ripencc": "https://ftp.ripe.net/pub/stats/ripencc/delegated-ripencc-latest",
}


def fetch(url: str, timeout: int = 30) -> str:
    print(f"fetching {url}", file=sys.stderr, flush=True)
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "israel-ip-blocker/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read()
    print(f"fetched {len(body)} bytes from {url}", file=sys.stderr, flush=True)
    return body.decode("utf-8", errors="replace")


def to_cidrs(start: str, count: int) -> list[str]:
    first = ipaddress.ip_address(start)
    last = ipaddress.ip_address(int(first) + count - 1)
    return [str(network) for network in ipaddress.summarize_address_range(first, last)]


def collect(timeout: int = 30) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    v4, v6 = set(), set()
    records: list[dict[str, Any]] = []

    for rir, url in RIR_FEEDS.items():
        before_v4, before_v6 = len(v4), len(v6)
        for line in fetch(url, timeout).splitlines():
            if not line or line.startswith("#"):
                continue
            fields = line.split("|")
            if len(fields) < 7 or fields[0] != rir:
                continue

            _, country, kind, start, value, date, status, *extra = fields
            if country.upper() != "IL" or kind not in {"ipv4", "ipv6"}:
                continue
            if status.lower() not in {"allocated", "assigned"}:
                continue

            networks = to_cidrs(start, int(value))
            (v4 if kind == "ipv4" else v6).update(networks)
            records.append({
                "rir": rir,
                "country": country,
                "type": kind,
                "start": start,
                "value": int(value),
                "date": date,
                "status": status,
                **({"extra": extra} if extra else {}),
            })

        print(
            f"feed contributed {len(v4) - before_v4} IPv4 and "
            f"{len(v6) - before_v6} IPv6 prefixes: {url}",
            file=sys.stderr,
            flush=True,
        )

    if not v4 and not v6:
        raise RuntimeError("all RIR feeds returned zero Israeli ranges")

    return (
        sorted(v4, key=ipaddress.ip_network),
        sorted(v6, key=ipaddress.ip_network),
        records,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--output", help="Write JSON to this file")
    parser.add_argument("--csv", action="store_true", help="Output CIDRs as CSV")
    parser.add_argument("--nft", action="store_true", help="Output an nftables set-refresh batch")
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    try:
        v4, v6, records = collect(args.timeout)
    except (OSError, UnicodeError, urllib.error.URLError, RuntimeError) as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        return 1

    if args.nft:
        print("flush set inet block_israel v4")
        print("flush set inet block_israel v6")
        if v4:
            print("add element inet block_israel v4 { " + ", ".join(v4) + " }")
        if v6:
            print("add element inet block_israel v6 { " + ", ".join(v6) + " }")
    elif args.csv:
        destination = open(args.output, "w", newline="", encoding="utf-8") if args.output else sys.stdout
        try:
            writer = csv.writer(destination)
            writer.writerow(["family", "cidr"])
            writer.writerows([["ipv4", cidr] for cidr in v4])
            writer.writerows([["ipv6", cidr] for cidr in v6])
        finally:
            if args.output:
                destination.close()
    else:
        payload = {
            "country": "IL",
            "ipv4": v4,
            "ipv6": v6,
            "records": records,
        }
        output = json.dumps(payload, indent=2) + "\n"
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(output)
        else:
            print(output, end="")

    print(f"collected {len(v4)} IPv4 and {len(v6)} IPv6 prefixes", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
