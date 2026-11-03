{ ... }: {
  networking.hostName = "foto-test";
  time.timeZone = "Europe/Prague";
  system.stateVersion = "26.05";
  nix.settings.experimental-features = [
    "nix-command"
    "flakes"
  ];
  services.openssh = {
    enable = true;
    authorizedKeysInHomedir = true;
    settings = {
      PermitRootLogin = "prohibit-password";
      PasswordAuthentication = false;
      KbdInteractiveAuthentication = false;
    };
  };
  systemd.settings.Manager.DefaultTimeoutStartSec = "900s";
  services.vpsfreePhotoShowPreview = {
    enable = false;
    virtualHost = "foto.crucio.cz";
    mountPath = "/kra";
  };
  services.nginx.virtualHosts."foto.crucio.cz".locations = {
    "= /kra".return = "308 https://foto.vpsfree.cz/$is_args$args";
    "^~ /kra/".extraConfig = ''
      rewrite ^/kra/(.*)$ https://foto.vpsfree.cz/$1 permanent;
    '';
  };
  services.vpsfreeGallery = {
    enable = true;
    hostName = "foto.crucio.cz";
    # Enable after the initial local installation and data/privacy checks.
    public = true;
    openFirewall = true;
    tls = true;
    installationMode = false;
    # Public browsing approved; Piwigo still authenticates upload/admin actions.
    basicAuthFile = null;
  };
}
