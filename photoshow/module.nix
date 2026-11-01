{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.vpsfreePhotoShowPreview;
  app = import ./package.nix { inherit pkgs; };
  tools = import ./tools.nix { inherit pkgs; };
in
{
  options.services.vpsfreePhotoShowPreview.enable = lib.mkEnableOption "isolated PhotoShow preview on 127.0.0.1:18085";
  config = lib.mkIf cfg.enable {
    # Seed a separate state copy before enabling. This never mounts the old web tree.
    systemd.services.photoshow-preview = {
      description = "Original PhotoShow on PHP 8.5 (isolated local preview)";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      environment = {
        PHOTOSHOW_APP = "${app}";
        PHOTOSHOW_TOOLS = "${tools}";
      };
      serviceConfig = {
        ExecStart = "${pkgs.python3}/bin/python3 ${./run-preview.py}";
        DynamicUser = true;
        User = "photoshow-preview";
        StateDirectory = "photoshow-preview";
        StateDirectoryMode = "0700";
        RuntimeDirectory = "photoshow-preview";
        RuntimeDirectoryMode = "0700";
        Restart = "on-failure";
        RestartSec = 5;
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ProtectKernelTunables = true;
        ProtectKernelModules = true;
        ProtectControlGroups = true;
        RestrictSUIDSGID = true;
        LockPersonality = true;
        CapabilityBoundingSet = "";
        RestrictAddressFamilies = [
          "AF_INET"
          "AF_UNIX"
          "AF_NETLINK"
        ];
        InaccessiblePaths = [
          "-/var/www"
          "-/var/lib/mysql"
          "-/var/lib/mysql-piwigo"
        ];
        MemoryMax = "1280M";
        TasksMax = 48;
      };
    };
  };
}
