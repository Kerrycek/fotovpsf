{
  config,
  lib,
  pkgs,
  ...
}:
let
  cfg = config.services.vpsfreeGallery;
  state = cfg.stateDirectory;
  # Patch-level security update while the pinned Nixpkgs still has 11.4.12.
  mariadb =
    (pkgs.mariadb.override {
      version = "11.4.13";
      hash = "sha256-G7JUsQbQp8qHHPoY+m4Y1LgKdDD57J0VcexCcaE975Y=";
      # This gallery uses InnoDB/MyISAM; avoid unused optional engines.
      withStorageMroonga = false;
      withStorageRocks = false;
    }).overrideAttrs
      (old: {
        cmakeFlags = old.cmakeFlags ++ [ "-DPLUGIN_DUCKDB=NO" ];
      });
  themeVersion = builtins.substring 0 12 (builtins.hashFile "sha256" ../theme/theme.css);
  faviconVersion = builtins.substring 0 12 (builtins.hashFile "sha256" ../assets/favicon.png);
  touchIconVersion = builtins.substring 0 12 (
    builtins.hashFile "sha256" ../assets/apple-touch-icon.png
  );
  skinName = "vpsfree-${builtins.substring 0 12 (builtins.hashFile "sha256" ../theme/skin.inc.php)}";
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
    cp ${../theme/skin.inc.php} "$out/themes/vpsfree/skins/${skinName}.inc.php"
    cp ${../theme/skin.css} "$out/themes/vpsfree/skins/${skinName}.css"
    cp ${../assets/vpsfree-white.png} "$out/themes/vpsfree/logo.png"
    cp ${../assets/favicon.png} "$out/favicon-${faviconVersion}.png"
    cp ${../assets/apple-touch-icon.png} "$out/apple-touch-icon-${touchIconVersion}.png"
    cp ${../theme/admin.css} "$out/admin-vpsfree.css"
    cp ${../theme/admin.js} "$out/admin-vpsfree.js"
    cp ${../theme/standard-pages.css} "$out/standard-vpsfree.css"
    # Keep every core password/API-key call on the same modern verifier and
    # every password/key login on one shared throttle (not the read/upload API).
    substituteInPlace "$out/include/functions_user.inc.php" \
      --replace-fail 'function pwg_password_hash(' 'function vpsfree_original_password_hash(' \
      --replace-fail 'function pwg_password_verify(' 'function vpsfree_original_password_verify(' \
      --replace-fail 'function try_log_user(' 'function vpsfree_original_try_log_user(' \
      --replace-fail 'function auth_key_login(' 'function vpsfree_original_auth_key_login(' \
      --replace-fail "if (!isset(\$_SESSION['fake_user_cache']) || \$is_verify_hash_changed)" "if (!isset(\$_SESSION['fake_user_cache']['password']) || \$is_verify_hash_changed || password_needs_rehash(\$_SESSION['fake_user_cache']['password'], PASSWORD_ARGON2ID, VPSFREE_ARGON_OPTIONS))"
    # Cookie-authenticated writes need a token even where upstream makes it
    # optional. Direct, validated API-key authentication has no ambient cookie.
    substituteInPlace "$out/include/ws_functions/pwg.categories.php" "$out/include/ws_functions/pwg.images.php" \
      --replace-fail "if (isset(\$params['pwg_token']) and get_pwg_token() != \$params['pwg_token'])" "if ((!isset(\$params['pwg_token']) and !defined('PWG_API_KEY_REQUEST')) or (isset(\$params['pwg_token']) and get_pwg_token() != \$params['pwg_token']))"
    # Versioned brand icons replace the bundled icon on every page type.
    for header in themes/vpsfree/template/header.tpl themes/default/template/header.tpl themes/standard_pages/template/header.tpl; do
      substituteInPlace "$out/$header" \
        --replace-fail '<link rel="shortcut icon" type="image/x-icon" href="{$ROOT_URL}{$themeconf.icon_dir}/favicon.ico">' '<link rel="icon" type="image/png" sizes="16x16" href="{$ROOT_URL}favicon-${faviconVersion}.png"><link rel="apple-touch-icon" sizes="171x171" href="{$ROOT_URL}apple-touch-icon-${touchIconVersion}.png">'
    done
    substituteInPlace "$out/admin/themes/default/template/header.tpl" \
      --replace-fail '<link rel="icon" type="image/svg+xml" href="{$ROOT_URL}{$themeconf.icon_dir}/piwigo.org-icon 1.svg">' '<link rel="icon" type="image/png" sizes="16x16" href="{$ROOT_URL}favicon-${faviconVersion}.png"><link rel="apple-touch-icon" sizes="171x171" href="{$ROOT_URL}apple-touch-icon-${touchIconVersion}.png">'
    substituteInPlace "$out/themes/vpsfree/themeconf.inc.php" \
      --replace-fail 'Theme Name: modus' 'Theme Name: vpsFree' \
      --replace-fail '$this->assign( array(' '$conf["modus_theme"]["skin"] = "${skinName}"; $themeconf["colorscheme"] = "dark"; $this->assign( array('
    # Piwigo inserts runtime CSS/head elements at "\n</head>"; preserve it.
    substituteInPlace "$out/themes/vpsfree/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}themes/vpsfree/theme.css?v=${themeVersion}">'$'\n'"</head>"
    substituteInPlace "$out/admin/themes/default/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}admin-vpsfree.css"><script src="{$ROOT_URL}admin-vpsfree.js" defer></script>'$'\n'"</head>" \
      --replace-fail '<div id="pwgHead">' '<div id="pwgHead"><button id="vpsfree-admin-menu" type="button" aria-controls="menubar" aria-expanded="false" aria-label="Otevřít menu">☰</button>'
    substituteInPlace "$out/themes/standard_pages/template/header.tpl" \
      --replace-fail '</head>' '<link rel="stylesheet" href="{$ROOT_URL}standard-vpsfree.css">'$'\n'"</head>"
    cat ${../php/gallery-view.php} >> "$out/themes/vpsfree/themeconf.inc.php"
    substituteInPlace "$out/themes/vpsfree/template/menubar.tpl" \
      --replace-fail '<dl style="float:none">' '<dl class="vpsfree-search">' \
      --replace-fail '<dl style="float:right;margin-top:3px">' '<dl class="vpsfree-account">' \
      --replace-fail '<dt style="font-size:100%;font-weight:normal;padding-left:15px{*to avoid loosing hover*}">' '<dt>' \
      --replace-fail '<dt style="font-size:100%;font-weight:normal">' '<dt>' \
      --replace-fail '{elseif $id=="mbTags"}' '{elseif $id=="mbCategories"}<dt><a href="{$ROOT_URL}index.php?/categories">{"Albums"|translate}</a></dt>{elseif $id=="mbTags"}'
    substituteInPlace "$out/themes/vpsfree/template/mainpage_categories.tpl" \
      --replace-fail '<img class=albImg' '<img loading="lazy" decoding="async" class=albImg' \
      --replace-fail '{if $item.nb_images}' '{if !empty($item.vpsfree_album_year)}{$item.vpsfree_album_year} · {/if}{if $item.nb_images}'
    cp ${../php/image-auth.php} "$out/image-auth.php"
    # Executable code is immutable. Core/plugin updates go through this flake.
  '';
  policy = pkgs.writeText "piwigo-policy.php" ''
    <?php
    require_once '${../php/authentication.php}';
    $conf['vpsfree_login_throttle_directory'] = '${state}/auth-throttle';
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
      mariadb
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
      "d ${state}/auth-throttle 0700 piwigo piwigo 1d"
      "L+ ${state}/local/config/config.inc.php - - - - ${policy}"
      "L+ ${state}/app - - - - ${app}"
    ];
    services.mysql = {
      enable = true;
      package = mariadb;
      # Deliberately independent of any pre-existing /var/lib/mysql on the target.
      dataDir = "/var/lib/mysql-piwigo";
      settings.mysqld = {
        skip-networking = true;
        local-infile = false;
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
        ; PHP's 2026-10-23 advisory recommends disabling this unused feature.
        session.upload_progress.enabled = Off
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
        "${state}/auth-throttle"
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
        mariadb
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
      serverTokens = false;
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
          add_header Content-Security-Policy "frame-ancestors 'self'; object-src 'none'; base-uri 'self'; form-action 'self'" always;
          ${lib.optionalString cfg.tls ''add_header Strict-Transport-Security "max-age=2592000" always;''}
        '';
        locations = {
          "= /favicon.ico".extraConfig = "return 302 /favicon-${faviconVersion}.png;";
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
