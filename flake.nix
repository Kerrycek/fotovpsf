{
  description = "Portable vpsFree photo gallery";
  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";
    vpsadminos.url = "github:vpsfreecz/vpsadminos";
  };
  outputs =
    inputs@{ nixpkgs, vpsadminos, ... }:
    {
      nixosModules.default = import ./nixos/gallery.nix;
      nixosModules.photoshowPreview = import ./photoshow/module.nix;
      nixosConfigurations.foto-test = nixpkgs.lib.nixosSystem {
        system = "x86_64-linux";
        modules = [
          vpsadminos.nixosModules.containerStable
          ./hosts/foto-test.nix
          ./nixos/gallery.nix
          ./photoshow/module.nix
        ];
        specialArgs = { inherit inputs; };
      };
    };
}
