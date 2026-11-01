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
  postUnpack = ''
    python3 ${./normalize.py} "$sourceRoot"
  '';
  patches = [ ./php85.patch ];
  postPatch = ''
    cp ${./Modern.php} src/classes/Modern.php
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
    rm -f "$out/inc/jquery.fileupload.js" "$out/inc/jquery.fileupload-ui.js" "$out/inc/fileupload-ui.css"
  '';
}
