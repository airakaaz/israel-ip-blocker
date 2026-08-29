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

- `fetch_il_ip_ranges.py` — shared RIR fetcher; outputs JSON or CIDR CSV
- `update-block-israel.py` — systemd runtime helper that applies fetched CIDRs to nftables
- `block-israel.service` — one-shot systemd service
- `block-israel.timer` — daily refresh timer
- `init-israel-blocker.sh` — non-Nix installer and activator

## Install

Run from this directory:

```bash
sudo ./init-israel-blocker.sh --permanent
```

`--permanent` copies the files to their system locations:

```text
/usr/local/libexec/fetch_il_ip_ranges.py
/usr/local/libexec/update-block-israel.py
/etc/systemd/system/block-israel.service
/etc/systemd/system/block-israel.timer
```

Without `--permanent`, the initializer creates symlinks from those system locations back to this directory. That is convenient for development, but moving or deleting this directory will break the service.

The initializer reloads systemd, enables the timer, and runs an initial update.

The fetcher and nftables updater are deliberately separate. The fetcher is reusable by both approaches. The standalone systemd unit uses `update-block-israel.py` for runtime firewall mutation; the NixOS module does not package that updater and instead declares the firewall structure in Nix, then pipes the fetcher's `--nft` output directly into nftables.

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

## NixOS flake module

The repository exposes a NixOS module as `nixosModules.default`. Add the flake as an input to your system configuration:

```nix
# flake.nix
inputs.israel-ip-blocker.url = "github:airakaaz/israel-ip-blocker";
```

Import and enable the module in the host configuration:

```nix
{ inputs, ... }:
{
  imports = [ inputs.israel-ip-blocker.nixosModules.default ];

  services.israel-ip-blocker.enable = true;
}
```

The module declaratively creates the `inet block_israel` nftables table, its IPv4/IPv6 interval sets, the input/output/forward drop chains, and the systemd service/timer. Its runtime refresh uses only the shared fetcher; the non-Nix `update-block-israel.py` is not part of the flake module.

The module creates `israel-ip-blocker.service` and a persistent daily `israel-ip-blocker.timer`. The service runs once at boot after the declarative nftables table is loaded, then refreshes the declared sets daily. Validate with `nixos-rebuild dry-build` before switching; enabling it changes the host firewall.
