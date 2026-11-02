"""Normalize the public 2014 source before applying the reviewed UTF-8 patch."""
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
for path in [root / 'index.php', root / 'inc/jquery.scrollTo.js', *(root / 'src').rglob('*.php'), *(root / 'src/stylesheets').glob('*.css')]:
    data = path.read_bytes()
    try:
        source = data.decode('utf-8')
    except UnicodeDecodeError:
        source = data.decode('latin1')
    path.write_text(source.replace('\r\n', '\n').rstrip('\n') + '\n')
