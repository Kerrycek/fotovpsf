{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.vpsfreeGallery;
  state = cfg.stateDirectory;
  php = pkgs.php84.buildEnv {
    extensions =
      { enabled, all }:
      enabled
      ++ (with all; [
        gd
        exif
        mysqli
        mbstring
        zip
        intl
        opcache
      ]);
  };
  source = pkgs.fetchurl {
    url = "https://piwigo.org/download/dlcounter.php?code=16.4.0";
    sha256 = "72c58a337a1a0639b6ad8dc8f5900a2781fc19091b60ae157eb2ee58c5431c17";
  };
  communitySource = pkgs.fetchurl {
    url = "https://piwigo.org/ext/download.php?rid=10708";
    sha256 = "a9c76b291ded738afe43b634dd3497550da2975f02770352c5e211f58817a860";
  };
  app = pkgs.runCommand "piwigo-vpsfree-16.4.0" { nativeBuildInputs = [ pkgs.unzip ]; } ''
    unzip -q ${source}
    mv piwigo "$out"
    chmod -R u+w "$out"
    unzip -q ${communitySource} -d "$out/plugins"
    rm -rf "$out/local" "$out/_data" "$out/upload" "$out/galleries"
    ln -s ${state}/local "$out/local"
    ln -s ${state}/_data "$out/_data"
    ln -s ${state}/upload "$out/upload"
    ln -s ${state}/galleries "$out/galleries"
    cp -r "$out/themes/modus" "$out/themes/vpsfree"
    cp ${../theme/theme.css} "$out/themes/vpsfree/theme.css"
    cp ${../assets/vpsfree-white.png} "$out/themes/vpsfree/logo.png"
    cp ${../theme/admin.css} "$out/admin-vpsfree.css"
    cp ${../theme/admin.js} "$out/admin-vpsfree.js"
    cp ${../theme/standard-pages.css} "$out/standard-vpsfree.css"
    substituteInPlace "$out/themes/vpsfree/themeconf.inc.php" \
      --replace-fail 'Theme Name: modus' 'Theme Name: vpsFree'
    substituteInPlace "$out/themes/vpsfree/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}themes/vpsfree/theme.css"></head>'
    substituteInPlace "$out/admin/themes/default/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}admin-vpsfree.css"><script src="{$ROOT_URL}admin-vpsfree.js" defer></script></head>' \
      --replace-fail '<div id="pwgHead">' '<div id="pwgHead"><button id="vpsfree-admin-menu" type="button" aria-controls="menubar" aria-expanded="false" aria-label="Otevřít menu">☰</button>'
    substituteInPlace "$out/themes/standard_pages/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}standard-vpsfree.css"></head>'
    cp ${../php/image-auth.php} "$out/image-auth.php"
    # Executable code is immutable. Core/plugin updates go through this flake.
  '';
  policy = pkgs.writeText "piwigo-policy.php" ''
    <?php
    $conf['gallery_title'] = 'Fotogalerie vpsFree.cz';
    $conf['page_banner'] = '<div class="vpsfree-brand"><a href="./"><img src="themes/vpsfree/logo.png" width="171" height="50" alt="vpsFree.cz"><small>Fotogalerie</small></a></div>';
    $conf['default_theme'] = 'vpsfree';
    $conf['default_language'] = 'cs_CZ';
    $conf['allow_user_registration'] = false;
    $conf['allow_user_customization'] = false;
    $conf['gallery_locked'] = false;
    $conf['original_url_protection'] = 'all';
    $conf['derivative_url_style'] = 2;
    $conf['picture_ext'] = array('jpg', 'jpeg', 'png', 'webp');
    $conf['file_ext'] = $conf['picture_ext'];
    $conf['upload_form_all_types'] = false;
    $conf['graphics_library'] = 'gd';
    $conf['show_php_errors'] = E_ALL & ~E_DEPRECATED;
    $conf['show_php_errors_on_frontend'] = false;
    $conf['enable_core_update'] = false;
    $conf['enable_extensions_install'] = false;
    $conf['send_bcc_mail_webmaster'] = false;
    $conf['check_for_updates'] = false;
    $conf['nb_image_page'] = 60;
  '';
in
{
  options.services.vpsfreeGallery = {
    enable = lib.mkEnableOption "vpsFree Piwigo gallery";
    hostName = lib.mkOption {
      type = lib.types.str;
      description = "Gallery virtual host name.";
    };
    public = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Listen on public interfaces instead of loopback.";
    };
    tls = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Use ACME TLS directly; leave disabled behind the production reverse proxy.";
    };
    openFirewall = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Open HTTP/HTTPS ports; leave disabled behind the existing restricted production proxy firewall.";
    };
    externalHTTPS = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "External URLs use HTTPS, including when TLS terminates on a trusted reverse proxy.";
    };
    trustedProxyAddresses = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Explicit proxy IPs allowed to supply the real client address.";
    };
    dailyBackup = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Create a consistent private on-host backup daily; arrange off-host retention before production.";
    };
    stateDirectory = lib.mkOption {
      type = lib.types.str;
      default = "/var/lib/piwigo";
      description = "Portable gallery state; transfer with a consistent MariaDB dump.";
    };
    basicAuthFile = lib.mkOption {
      type = lib.types.nullOr lib.types.path;
      default = null;
      description = "Optional root-managed htpasswd file protecting the test gallery.";
    };
    installationMode = lib.mkOption {
      type = lib.types.bool;
      default = false;
      description = "Allow installer only from loopback; disable after initial installation.";
    };
  };
  config = lib.mkIf cfg.enable {
    assertions = [
      {
        assertion = !cfg.tls || cfg.public;
        message = "Gallery TLS requires public listening.";
      }
    ];
    users.groups.piwigo = { };
    users.users.piwigo = {
      isSystemUser = true;
      group = "piwigo";
      home = state;
    };
    environment.systemPackages = [
      php
      pkgs.mariadb
      pkgs.python3
      pkgs.unzip
      pkgs.git
      pkgs.rsync
      pkgs.imagemagick
    ];
    systemd.tmpfiles.rules = [
      "d ${state} 0711 root root -"
      "d ${state}/local 0750 root piwigo -"
      "d ${state}/local/config 0750 ${if cfg.installationMode then "piwigo" else "root"} piwigo -"
      "d ${state}/_data 0750 piwigo nginx -"
      "d ${state}/upload 0750 piwigo nginx -"
      "d ${state}/galleries 0750 piwigo nginx -"
      "d ${state}/sessions 0700 piwigo piwigo -"
      "L+ ${state}/local/config/config.inc.php - - - - ${policy}"
      "L+ ${state}/app - - - - ${app}"
    ];
    services.mysql = {
      enable = true;
      package = pkgs.mariadb;
      # Deliberately independent of any pre-existing /var/lib/mysql on the target.
      dataDir = "/var/lib/mysql-piwigo";
      settings.mysqld = {
        skip-networking = true;
        character-set-server = "utf8mb4";
        collation-server = "utf8mb4_unicode_ci";
      };
      ensureDatabases = [ "piwigo" ];
      ensureUsers = [
        {
          name = "piwigo";
          ensurePermissions = {
            "piwigo.*" = "ALL PRIVILEGES";
          };
        }
      ];
    };
    services.phpfpm.pools.piwigo = {
      user = "piwigo";
      group = "piwigo";
      phpPackage = php;
      settings = {
        "listen.owner" = "nginx";
        "listen.group" = "nginx";
        "listen.mode" = "0600";
        "pm" = "dynamic";
        "pm.max_children" = 4;
        "pm.start_servers" = 2;
        "pm.min_spare_servers" = 1;
        "pm.max_spare_servers" = 3;
        "pm.max_requests" = 500;
        "catch_workers_output" = true;
      };
      phpOptions = ''
        expose_php = Off
        display_errors = Off
        log_errors = On
        date.timezone = ${if config.time.timeZone == null then "UTC" else config.time.timeZone}
        memory_limit = 512M
        upload_max_filesize = 40M
        post_max_size = 45M
        max_file_uploads = 20
        max_execution_time = 120
        session.save_path = ${state}/sessions
        session.cookie_httponly = On
        session.cookie_samesite = Lax
        session.use_strict_mode = On
        session.cookie_secure = ${if cfg.externalHTTPS || cfg.tls then "On" else "Off"}
        mysqli.default_socket = /run/mysqld/mysqld.sock
        sendmail_path = /run/current-system/sw/bin/false
      '';
    };
    systemd.services.phpfpm-piwigo.serviceConfig = {
      ProtectSystem = lib.mkForce "strict";
      ReadWritePaths = [
        "${state}/_data"
        "${state}/upload"
        "${state}/galleries"
        "${state}/sessions"
      ];
      RestrictAddressFamilies = lib.mkForce [ "AF_UNIX" ];
      NoNewPrivileges = true;
    };
    systemd.services.piwigo-backup = lib.mkIf cfg.dailyBackup {
      description = "Consistent private Piwigo backup";
      after = [ "mysql.service" ];
      environment.FOTOVPSF_STATE_DIRECTORY = state;
      path = [
        pkgs.coreutils
        pkgs.util-linux
        pkgs.gnutar
        pkgs.gzip
        pkgs.mariadb
        pkgs.git
        pkgs.systemd
      ];
      serviceConfig = {
        Type = "oneshot";
        UMask = "0077";
      };
      script = "${pkgs.bash}/bin/bash ${../scripts/backup.sh} /var/backups/piwigo";
    };
    systemd.timers.piwigo-backup = lib.mkIf cfg.dailyBackup {
      wantedBy = [ "timers.target" ];
      timerConfig = {
        OnCalendar = "*-*-* 03:15:00";
        RandomizedDelaySec = "5m";
        Persistent = true;
      };
    };
    services.nginx = {
      enable = true;
      recommendedTlsSettings = true;
      recommendedOptimisation = true;
      appendHttpConfig = ''
        limit_req_zone $binary_remote_addr zone=gallery_login:10m rate=10r/m;
        limit_req_zone $binary_remote_addr zone=gallery_api:10m rate=10r/s;
      ''
      + lib.optionalString (cfg.trustedProxyAddresses != [ ]) ''
        real_ip_header X-Forwarded-For;
        real_ip_recursive on;
        ${lib.concatMapStringsSep "\n" (address: "set_real_ip_from ${address};") cfg.trustedProxyAddresses}
      '';
      virtualHosts.${cfg.hostName} = {
        root = app;
        forceSSL = cfg.tls;
        enableACME = cfg.tls;
        basicAuthFile = cfg.basicAuthFile;
        listen = lib.mkIf (!cfg.public) [
          {
            addr = "127.0.0.1";
            port = 8080;
          }
        ];
        extraConfig = ''
          client_max_body_size 45m;
          autoindex off;
          add_header X-Content-Type-Options nosniff always;
          add_header X-Frame-Options SAMEORIGIN always;
          add_header Referrer-Policy same-origin always;
          add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
        '';
        locations = {
          "/".extraConfig = "index index.php; try_files $uri $uri/ /index.php?$query_string;";
          "~ (^|/)\\.".extraConfig = "return 404;";
          "^~ /local/".extraConfig = "return 404;";
          "^~ /galleries/".extraConfig = "return 404;";
          "^~ /upload/".extraConfig = "return 404;";
          "^~ /_data/logs/".extraConfig = "return 404;";
          "^~ /_data/templates_c/".extraConfig = "return 404;";
          "^~ /_data/".extraConfig = "return 404;";
          "^~ /_data/combined/".extraConfig = ''
            if ($uri !~* \\.(css|js)$) { return 404; }
            try_files $uri =404;
          '';
          "^~ /_data/i/".extraConfig = ''
            auth_request /__gallery_image_auth;
            try_files $uri =404;
          '';
          "= /image-auth.php".extraConfig = "return 404;";
          "= /__gallery_image_auth".extraConfig = ''
            internal;
            include ${pkgs.nginx}/conf/fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root/image-auth.php;
            fastcgi_param GALLERY_ORIGINAL_URI $request_uri;
            fastcgi_param HTTPS ${if cfg.externalHTTPS || cfg.tls then "on" else "off"};
            fastcgi_pass_request_body off;
            fastcgi_param CONTENT_LENGTH "";
            fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
          '';
          "= /i.php".extraConfig = ''
            auth_request /__gallery_image_auth;
            include ${pkgs.nginx}/conf/fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root/i.php;
            fastcgi_param HTTPS ${if cfg.externalHTTPS || cfg.tls then "on" else "off"};
            fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
          '';
          "^~ /install/".extraConfig = "return 404;";
          "= /install.php".extraConfig =
            if cfg.installationMode then
              ''
                allow 127.0.0.1; deny all;
                include ${pkgs.nginx}/conf/fastcgi_params;
                fastcgi_param SCRIPT_FILENAME $document_root/install.php;
                fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
              ''
            else
              "return 404;";
          "= /upgrade.php".extraConfig = "return 404;";
          "= /identification.php".extraConfig = ''
            limit_req zone=gallery_login burst=10 nodelay;
            limit_req_status 429;
            include ${pkgs.nginx}/conf/fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root/identification.php;
            fastcgi_param HTTPS ${if cfg.externalHTTPS || cfg.tls then "on" else "off"};
            fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
          '';
          "= /ws.php".extraConfig = ''
            limit_req zone=gallery_api burst=40 nodelay;
            limit_req_status 429;
            include ${pkgs.nginx}/conf/fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root/ws.php;
            fastcgi_param HTTPS ${if cfg.externalHTTPS || cfg.tls then "on" else "off"};
            fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
            fastcgi_read_timeout 120s;
          '';
          "~ \\.php$".extraConfig = ''
            try_files $uri =404;
            include ${pkgs.nginx}/conf/fastcgi_params;
            fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
            fastcgi_param HTTPS ${if cfg.externalHTTPS || cfg.tls then "on" else "off"};
            fastcgi_pass unix:${config.services.phpfpm.pools.piwigo.socket};
            fastcgi_read_timeout 120s;
          '';
        };
      };
    };
    networking.firewall.allowedTCPPorts = lib.mkIf (cfg.public && cfg.openFirewall) (
      [ 80 ] ++ lib.optional cfg.tls 443
    );
    security.acme = lib.mkIf cfg.tls {
      acceptTerms = true;
      defaults.email = "admin@crucio.cz";
    };
  };
}
