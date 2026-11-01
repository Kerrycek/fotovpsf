{ pkgs }:
pkgs.symlinkJoin {
  name = "photoshow-preview-tools";
  paths = [
    (import ./runtime.nix { inherit pkgs; })
    pkgs.nginx
    pkgs.python3
    pkgs.coreutils
    pkgs.bash
  ];
}
