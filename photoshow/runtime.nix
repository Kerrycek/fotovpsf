{ pkgs }:
pkgs.php85.buildEnv {
  extensions =
    { enabled, all }:
    enabled
    ++ (with all; [
      gd
      exif
      mbstring
      zip
    ]);
  extraConfig = ''
    expose_php = Off
    display_errors = Off
    log_errors = On
    error_reporting = E_ALL
    memory_limit = 512M
    upload_max_filesize = 48M
    post_max_size = 64M
    session.use_strict_mode = 1
    session.cookie_httponly = 1
    session.cookie_samesite = Lax
    session.upload_progress.enabled = Off
    allow_url_fopen = Off
    allow_url_include = Off
  '';
}
