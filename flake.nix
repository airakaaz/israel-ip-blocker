{
  description = "Daily nftables blocklist for Israeli IP allocations";

  outputs = { self }: {
    nixosModules.default = import ./nixos-module.nix;
  };
}
