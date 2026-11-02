"""Supervise isolated Nginx and PHP-FPM; never reload the production web server."""
import pathlib
import subprocess
import signal
import time
import os
import socket
import http.client

root=pathlib.Path('/run/photoshow-preview')
app=pathlib.Path(os.environ.get('PHOTOSHOW_APP','/srv/photoshow-php85-app')).resolve()
public_url=os.environ.get('PHOTOSHOW_PUBLIC_URL', '')
base_path=os.environ.get('PHOTOSHOW_BASE_PATH', '/')
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
env[PHOTOSHOW_PUBLIC_URL]={public_url}
env[PHOTOSHOW_BASE_PATH]={base_path}
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
    set_real_ip_from 127.0.0.1;
    real_ip_header X-Real-IP;
    add_header X-Content-Type-Options nosniff always;
    location = / { rewrite ^ /index.php last; }
    location = /index.php {
      include TOOLS/conf/fastcgi_params;
      fastcgi_param SCRIPT_FILENAME APP/index.php;
      fastcgi_param SERVER_NAME localhost;
      fastcgi_param HTTPS EXTERNAL_HTTPS;
      fastcgi_pass unix:/run/photoshow-preview/php.sock;
      fastcgi_read_timeout 70s;
      fastcgi_hide_header X-Powered-By;
    }
    location ~ ^/(?:inc|src/(?:stylesheets|js)|user/themes)/[^?]+\\.(?:css|js|png|jpg|jpeg|gif|ico|woff2?|ttf|otf|eot|svg)$ { try_files $uri =404; }
    location / { return 404; }
  }
}
'''.replace('TOOLS',str(tools)).replace('APP',str(app)).replace('EXTERNAL_HTTPS', 'on' if public_url.startswith('https://') else 'off'))
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
    nginx=subprocess.Popen([str(tools/'bin/nginx'),'-e','stderr','-c',str(root/'nginx.conf'),'-p',str(root)]);processes.append(nginx)
    # A successful systemctl start must mean both Nginx and PHP can serve a page.
    deadline=time.monotonic()+20
    ready=False
    while time.monotonic()<deadline and not stopping:
        if any(p.poll() is not None for p in processes):raise RuntimeError('Preview child exited before readiness')
        connection=http.client.HTTPConnection('127.0.0.1',18085,timeout=1)
        try:
            connection.request('GET','/')
            response=connection.getresponse();response.read()
            if response.status in (200,403):ready=True;break
        except OSError:pass
        finally:connection.close()
        time.sleep(.05)
    if not ready and not stopping:raise RuntimeError('Preview did not become ready')
    if ready and os.environ.get('NOTIFY_SOCKET'):
        address=os.environ['NOTIFY_SOCKET']
        if address.startswith('@'):address='\0'+address[1:]
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as notification:
            notification.sendto(b'READY=1',address)

    while all(p.poll() is None for p in processes):time.sleep(.5)
    if not stopping:raise RuntimeError('Preview child exited unexpectedly')
finally:
    stop()
    for process in processes:
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()
