# Israel IP Blocker

A small `systemd` + `nftables` blocklist updater for IP allocations registered to Israel (`IL`). It fetches the latest delegated statistics from all five Regional Internet Registries (RIRs), converts the ranges to CIDRs, and refreshes nftables sets daily.

> **Important:** RIR allocation data is not the same as live BGP routing data. A range may be registered to Israel but unused, announced elsewhere, or not currently routed. Blocking the list can also block legitimate services and users.

## Requirements

- Linux with `systemd`
- `nftables` and the `nft` command
- Python 3 with only standard-library modules
- Root access for installation and firewall updates
- Network access to the RIR feeds

## Files

- `update-block-israel.py` — fetches RIR data and updates nftables
- `block-israel.service` — one-shot systemd service
- `block-israel.timer` — daily refresh timer
- `init-israel-blocker.sh` — installer and activator

## Install

Run from this directory:

```bash
sudo ./init-israel-blocker.sh --permanent
```

`--permanent` copies the files to their system locations:

```text
/usr/local/libexec/update-block-israel.py
/etc/systemd/system/block-israel.service
/etc/systemd/system/block-israel.timer
```

Without `--permanent`, the initializer creates symlinks from those system locations back to this directory. That is convenient for development, but moving or deleting this directory will break the service.

The initializer reloads systemd, enables the timer, and runs an initial update.

## Check status and logs

```bash
systemctl status block-israel.timer
systemctl list-timers block-israel.timer
journalctl -u block-israel.service -n 100 --no-pager
```

Run a manual refresh:

```bash
sudo systemctl start block-israel.service
```

Inspect the loaded sets:

```bash
sudo nft list table inet block_israel
```

## What is blocked?

The nftables table drops:

- Incoming traffic whose source is in the list
- Outgoing traffic whose destination is in the list
- Forwarded traffic in either direction
- Both IPv4 and IPv6 ranges

The table uses an `accept` policy and adds only the blocklist rules, so it does not replace an existing firewall policy.

## Troubleshooting

The updater writes verbose diagnostics to stderr, which systemd records in the journal. Look for:

```bash
journalctl -u block-israel.service --since today --no-pager
```

If an update fails while downloading or parsing a feed, the existing nftables sets are left unchanged. The service must be rerun after fixing the problem:

```bash
sudo systemctl restart block-israel.service
```

The RIR feeds used are:

- AFRINIC
- APNIC
- ARIN
- LACNIC
- RIPE NCC

This project is intended for defensive network administration. Review the generated ranges before deploying it on a production system.
