"""Supervise isolated Nginx and PHP-FPM; never reload the production web server."""
import pathlib
import subprocess
import signal
import time
import os

root=pathlib.Path('/run/photoshow-preview')
app=pathlib.Path(os.environ.get('PHOTOSHOW_APP','/srv/photoshow-php85-app')).resolve()
tools=pathlib.Path(os.environ.get('PHOTOSHOW_TOOLS','/srv/photoshow-php85-tools')).resolve()
(root/'fpm.conf').write_text(f'''[global]
error_log=/var/lib/photoshow-preview/error.log
daemonize=no
[photoshow-preview]
listen={root}/php.sock
listen.mode=0600
pm=ondemand
pm.max_children=2
pm.process_idle_timeout=15s
pm.max_requests=200
request_terminate_timeout=60s
catch_workers_output=yes
clear_env=yes
php_admin_value[session.save_path]=/var/lib/photoshow-preview/sessions
php_admin_flag[display_errors]=off
php_admin_flag[log_errors]=on
php_admin_value[error_log]=/var/lib/photoshow-preview/error.log
''')
(root/'nginx.conf').write_text('''daemon off;
pid /run/photoshow-preview/nginx.pid;
error_log stderr warn;
worker_processes 1;
events { worker_connections 128; }
http {
  access_log off;
  server_tokens off;
  include TOOLS/conf/mime.types;
  default_type application/octet-stream;
  client_body_temp_path /run/photoshow-preview/body;
  fastcgi_temp_path /run/photoshow-preview/fastcgi;
  client_max_body_size 64m;
  server {
    listen 127.0.0.1:18085;
    server_name localhost;
    root APP;
    add_header X-Content-Type-Options nosniff always;
    location = / { rewrite ^ /index.php last; }
    location = /index.php {
      include TOOLS/conf/fastcgi_params;
      fastcgi_param SCRIPT_FILENAME APP/index.php;
      fastcgi_param SERVER_NAME localhost;
      fastcgi_pass unix:/run/photoshow-preview/php.sock;
      fastcgi_read_timeout 70s;
      fastcgi_hide_header X-Powered-By;
    }
    location ~ ^/(?:inc|src/(?:stylesheets|js)|user/themes)/[^?]+\\.(?:css|js|png|jpg|jpeg|gif|ico|woff2?|ttf|otf|eot|svg)$ { try_files $uri =404; }
    location / { return 404; }
  }
}
'''.replace('TOOLS',str(tools)).replace('APP',str(app)))
processes=[]
stopping=False
def stop(*_):
    global stopping
    stopping=True
    for process in processes:
        if process.poll() is None: process.terminate()
signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
try:
    php=subprocess.Popen([str(tools/'bin/php-fpm'),'-y',str(root/'fpm.conf')]);processes.append(php)
    for _ in range(100):
        if (root/'php.sock').exists():break
        if php.poll() is not None:raise RuntimeError('FPM failed')
        time.sleep(.05)
    nginx=subprocess.Popen([str(tools/'bin/nginx'),'-c',str(root/'nginx.conf'),'-p',str(root)]);processes.append(nginx)
    while all(p.poll() is None for p in processes):time.sleep(.5)
    if not stopping:raise RuntimeError('Preview child exited unexpectedly')
finally:
    stop()
    for process in processes:
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
