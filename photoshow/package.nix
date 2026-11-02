{ pkgs }:
pkgs.stdenvNoCC.mkDerivation {
  pname = "vpsfree-photoshow";
  version = "3.0-php85";
  src = pkgs.fetchurl {
    name = "photoshow-20140715.tar.gz";
    url = "https://codeload.github.com/thibaud-rohmer/PhotoShow/tar.gz/3d15c06155af6c2340954d4b5a589b19bebf4aac";
    hash = "sha256-D526/ktl/rcZLJAESCGYeinbA2rz3ZoOCAofXMst0fQ=";
  };
  nativeBuildInputs = [ pkgs.python3 ];
  jquery = pkgs.fetchurl {
    url = "https://code.jquery.com/jquery-4.0.0.min.js";
    hash = "sha256-OaVG6prZf4v69dPg6PhVattBXkcOWQB62pdZ3ORyrao=";
  };
  jqueryMigrate = pkgs.fetchurl {
    url = "https://code.jquery.com/jquery-migrate-4.0.2.min.js";
    hash = "sha256-LzsJUf1meVLJnOtz5tjDaNu/2+KYX4BI6ytmi4nkEQU=";
  };
  postUnpack = ''
    python3 ${./normalize.py} "$sourceRoot"
  '';
  patches = [ ./php85.patch ];
  postPatch = ''
    cp ${./Modern.php} src/classes/Modern.php
    mkdir -p src/security
    cp ${./login-gate.php} src/security/login-gate.php
    cp "$jquery" inc/jquery.js
    cp "$jqueryMigrate" inc/jquery-migrate.js
    cp ${./modern.js} inc/modern.js
    cp ${./upload.js} src/js/admin.js
    cp ${./preview.css} inc/preview.css
    cp ${../assets/favicon.png} inc/vpsfree-favicon.png
    cp ${./config.php} config.php
  '';
  installPhase = ''
    mkdir -p "$out"
    cp -r index.php README.md src inc user config.php "$out/"
    rm -rf "$out/src/tests" "$out/src/scripts"
    rm -f "$out/inc/jquery.fileupload.js" "$out/inc/jquery.fileupload-ui.js" "$out/inc/fileupload-ui.css" "$out/inc/jquery-ui.js"
  '';
}
