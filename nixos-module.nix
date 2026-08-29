{ config, lib, pkgs, ... }:

let
  cfg = config.services.israel-ip-blocker;
  fetcher = pkgs.writeText "israel-ip-blocker-fetch.py"
    (builtins.readFile ./fetch_il_ip_ranges.py);
  refresh = pkgs.writeShellScript "israel-ip-blocker-refresh" ''
    set -o pipefail
    ${pkgs.python3}/bin/python3 ${fetcher} --nft |
      ${pkgs.nftables}/bin/nft -f -
  '';
in
{
  options.services.israel-ip-blocker.enable = lib.mkEnableOption
    "blocking traffic to and from Israeli RIR allocations";

  config = lib.mkIf cfg.enable {
    networking.nftables.enable = true;
    networking.nftables.tables.block_israel = {
      family = "inet";
      content = ''
        set v4 {
          type ipv4_addr;
          flags interval;
        }

        set v6 {
          type ipv6_addr;
          flags interval;
        }

        chain input {
          type filter hook input priority -100;
          policy accept;
          ip saddr @v4 drop
          ip6 saddr @v6 drop
        }

        chain output {
          type filter hook output priority -100;
          policy accept;
          ip daddr @v4 drop
          ip6 daddr @v6 drop
        }

        chain forward {
          type filter hook forward priority -100;
          policy accept;
          ip saddr @v4 drop
          ip6 saddr @v6 drop
          ip daddr @v4 drop
          ip6 daddr @v6 drop
        }
      '';
    };

    systemd.services.israel-ip-blocker = {
      description = "Update nftables blocklist for Israeli IP allocations";
      wants = [ "network-online.target" "nftables.service" ];
      after = [ "network-online.target" "nftables.service" ];
      wantedBy = [ "multi-user.target" ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = refresh;
        User = "root";
        Environment = "PATH=${lib.makeBinPath [ pkgs.nftables ]}";
      };
    };

    systemd.timers.israel-ip-blocker = {
      description = "Daily Israeli IP allocation blocklist update";
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "daily";
        Persistent = true;
        RandomizedDelaySec = "15m";
        Unit = "israel-ip-blocker.service";
      };
    };
  };
}
