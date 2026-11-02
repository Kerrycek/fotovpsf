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
  options.services.vpsfreePhotoShowPreview = {
    enable = lib.mkEnableOption "isolated PhotoShow on PHP 8.5";
    virtualHost = lib.mkOption {
      type = lib.types.nullOr lib.types.str;
      default = null;
      description = "Existing TLS virtual host to mount the gallery on; null keeps loopback-only access.";
    };
    mountPath = lib.mkOption {
      type = lib.types.strMatching "/[a-zA-Z0-9_-]+";
      default = "/kra";
      description = "Public path without trailing slash. Cookies and canonical URLs are scoped here; existing native gallery paths are retained.";
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion =
          cfg.virtualHost == null || config.services.nginx.virtualHosts.${cfg.virtualHost}.forceSSL;
        message = "Public PhotoShow requires an existing TLS virtual host.";
      }
    ];
    services.nginx.virtualHosts = lib.mkIf (cfg.virtualHost != null) {
      ${cfg.virtualHost}.locations = {
        "= ${cfg.mountPath}".extraConfig = "return 308 ${cfg.mountPath}/$is_args$args;";
        "^~ ${cfg.mountPath}/" = {
          proxyPass = "http://127.0.0.1:18085/";
          extraConfig = ''
            client_max_body_size 64m;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-Proto https;
            proxy_set_header X-Forwarded-For $remote_addr;
            proxy_read_timeout 90s;
            proxy_redirect off;
          '';
        };
      };
    };
    systemd.tmpfiles.rules = [
      "e /var/lib/photoshow-preview/auth-throttle - - - 1d"
      "d /var/backups/photoshow-port 0700 root root -"
    ];
    # Snapshot the native file/XML state independently of the Piwigo database.
    systemd.services.photoshow-backup = {
      description = "Consistent PhotoShow checkpoint with isolated restore verification";
      path = [ pkgs.systemd ];
      serviceConfig = {
        Type = "oneshot";
        ExecStart = "${pkgs.python3}/bin/python3 ${./backup-preview.py}";
        UMask = "0077";
        NoNewPrivileges = true;
        PrivateTmp = true;
        ProtectSystem = "strict";
        ProtectHome = true;
        ReadWritePaths = [ "/var/backups/photoshow-port" ];
      };
    };
    systemd.timers.photoshow-backup = {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 03:35:00";
        RandomizedDelaySec = "5m";
        Persistent = true;
      };
    };
    # Seed a separate state copy before enabling. This never mounts the old web tree.
    systemd.services.photoshow-preview = {
      description = "Original PhotoShow on PHP 8.5 (isolated local preview)";
      wantedBy = [ "multi-user.target" ];
      after = [ "network.target" ];
      environment = {
        PHOTOSHOW_APP = "${app}";
        PHOTOSHOW_TOOLS = "${tools}";
      }
      // lib.optionalAttrs (cfg.virtualHost != null) {
        PHOTOSHOW_PUBLIC_URL = "https://${cfg.virtualHost}${cfg.mountPath}/";
        PHOTOSHOW_BASE_PATH = "${cfg.mountPath}/";
      };
      serviceConfig = {
        Type = "notify";
        NotifyAccess = "main";
        TimeoutStartSec = "30s";
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
