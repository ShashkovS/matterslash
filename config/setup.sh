# Заменить:
# matterslash (например, vmsh)
# proj179.ru (например, shashkovs.ru или proj179.ru)
# matterslash (имя проекта, его папка, юзер, адрес и т.п.)
# dbpassword (пароль базы)
# mikheev (кому ещё дать доступ)
# https://github.com/ShashkovS/matterslash.git (репозиторий)

nostopitdontrun
exit

adduser mikheev
passwd mikheev
  ...
usermod -aG wheel mikheev

# Настраиваем dns для нового поддомена
# ...


# Настраиваем ssl для нового поддомена
certbot --nginx -d matterslash.proj179.ru
   # /etc/letsencrypt/live/matterslash.proj179.ru/fullchain.pem
   # Your key file has been saved at:
   # /etc/letsencrypt/live/matterslash.proj179.ru/privkey.pem


# Содержимое каждого сайта будет находиться в собственном каталоге, поэтому создаём нового пользователя 
useradd matterslash -b /web/ -m -U -s /bin/false

# Делаем каталоги для данных сайта (файлы сайта, логи и временные файлы):
mkdir -p -m 754 /web/matterslash/logs
mkdir -p -m 777 /web/matterslash/tmp

# Делаем юзера и его группу владельцем  всех своих папок
chown -R matterslash:matterslash /web/matterslash/

# Изменяем права доступа на каталог
chmod 755 /web/matterslash

# Чтобы Nginx получил доступ к файлам сайта, добавим пользователя nginx в группу
usermod -a -G matterslash nginx


# виртуальное окружение
cd /web/matterslash
python3.9 -m venv --without-pip matterslash_env
source /web/matterslash/matterslash_env/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3.9
deactivate
source /web/matterslash/matterslash_env/bin/activate
pip install flask gunicorn werkzeug pyjwt requests
deactivate

# Клонируем репу
cd /web/matterslash
git clone https://github.com/ShashkovS/matterslash.git

# Запускаем стартовое


# Настраиваем systemd для поддержания приложения в рабочем состоянии
# Начинаем с описания сервиса
echo '
[Unit]
Description=Gunicorn instance to serve matterslash
Requires=gunicorn.matterslash.socket
After=network.target

[Service]
PIDFile=/web/matterslash/matterslash.pid
Restart=on-failure
User=matterslash
Group=nginx
RuntimeDirectory=gunicorn
WorkingDirectory=/web/matterslash/matterslash
Environment="PATH=/web/matterslash/matterslash_env/bin"
ExecStart=/web/matterslash/matterslash_env/bin/gunicorn  --pid /web/matterslash/matterslash.pid  --workers 1  --bind unix:/web/matterslash/matterslash.socket  -m 007  matterslash_app:app
ExecReload=/bin/kill -s HUP $MAINPID
ExecStop=/bin/kill -s TERM $MAINPID
PrivateTmp=true

[Install]
WantedBy=multi-user.target
' > /etc/systemd/system/gunicorn.matterslash.service

# Теперь socket-файл. В нём написано, что если в сокет упадут какие-либо данные, то нужно запустить сервис, если он вдруг не запущен
echo '[Unit]
Description=gunicorn.matterslash.socket

[Socket]
ListenStream=/web/matterslash/matterslash.socket

[Install]
WantedBy=sockets.target
' >  /etc/systemd/system/gunicorn.matterslash.socket

# Путь к конфигаем
echo 'd /run/gunicorn 0755 matterslash nginx -
' > /etc/tmpfiles.d/gunicorn.matterslash.conf



# Говорим, что нужен автозапуск
sudo systemctl enable gunicorn.matterslash.socket
# Запускаем
sudo systemctl restart gunicorn.matterslash.socket
# Проверяем
curl --unix-socket /web/matterslash/matterslash.socket http

# Логи
journalctl -u gunicorn.matterslash.service
systemctl status gunicorn.matterslash.service

# Настраиваем nginx (здесь настройки СТРОГО отдельного домена или поддомена). Если хочется держать в папке, то настраивать nginx нужно по-другому
echo '
    server {
        listen       80;
        listen       [::]:80;
        server_name matterslash.proj179.ru;
        return 301 https://$host$request_uri;
    }

    server {
        listen [::]:443 ssl http2; # managed by Certbot
        listen 443 ssl http2; # managed by Certbot
        server_name matterslash.proj179.ru; # managed by Certbot
        root         /web/matterslash/matterslash;

        ssl_certificate /etc/letsencrypt/live/matterslash.proj179.ru/fullchain.pem; # managed by Certbot
        ssl_certificate_key /etc/letsencrypt/live/matterslash.proj179.ru/privkey.pem; # managed by Certbot
        include /etc/letsencrypt/options-ssl-nginx.conf; # managed by Certbot
        ssl_dhparam /etc/ssl/certs/dhparam.pem;
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains; preload" always;

        location / {
            proxy_set_header Host $http_host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_pass http://unix:/web/matterslash/matterslash.socket;        
        }

        location /static {
            alias /web/matterslash/matterslash/static;
            try_files $uri =404;
        }

        location /matterslash/cgi-bin/ {
         access_log /web/matterslash/logs/nginx_access.log;
         error_log /web/matterslash/logs/nginx_error.log;
         include fastcgi_params;
         fastcgi_param AUTH_USER $remote_user;
         fastcgi_param REMOTE_USER $remote_user;
         fastcgi_pass unix:/var/run/fcgiwrap.socket;
         fastcgi_param SCRIPT_FILENAME /web$fastcgi_script_name;
         fastcgi_param PATH_INFO $fastcgi_script_name;
        }

        error_page 404 /404.html;
            location = /40x.html {
        }

        error_page 500 502 503 504 /50x.html;
            location = /50x.html {
        }
    }
' > /etc/nginx/conf.d/matterslash.conf

# Проверяем корректность конфига. СУПЕР-ВАЖНО!
nginx -t
# Перезапускаем nginx
systemctl reload nginx.service

# Даём права дирижаблю
usermod -a -G matterslash mikheev





# Создаём ключ для ssh+github
mkdir /web/matterslash/.ssh
chmod 0700 /web/matterslash/.ssh
touch /web/matterslash/.ssh/authorized_keys
chmod 0644 /web/matterslash/.ssh/authorized_keys
ssh-keygen -t rsa -b 4096 -C "matterslash@matterslash.proj179.ru"
  /web/matterslash/.ssh/matterslash_rsa_key_for_github
ssh-keygen -t rsa -b 4096 -C "matterslash@matterslash.proj179.ru"
  /web/matterslash/.ssh/matterslash_rsa_key_for_ssh

cat /web/matterslash/.ssh/matterslash_rsa_key_for_github.pub >> /web/matterslash/.ssh/authorized_keys
cat /web/matterslash/.ssh/matterslash_rsa_key_for_ssh.pub >> /web/matterslash/.ssh/authorized_keys
# выгружаем matterslash_rsa_key_for_ssh наружу
rm -rf /web/matterslash/.ssh/matterslash_rsa_key_for_ssh*

# Копируем ключ для гитхаба
cat /web/matterslash/.ssh/matterslash_rsa_key_for_github.pub
# Вставляем в deploy keys https://github.com/ShashkovS/matterslash/settings/keys

# Создаём настройки для github'а
touch /web/matterslash/.ssh/config
chmod 0644 /web/matterslash/.ssh/config
echo 'Host github.com
  IdentityFile /web/matterslash/.ssh/matterslash_rsa_key_for_github' > /web/matterslash/.ssh/config

# Ещё добавляем дирижаблю
cat /web/matterslash/.ssh/matterslash_rsa_key_for_github.pub >> /home/mikheev/.ssh/authorized_keys
touch /home/mikheev/.ssh/config
chmod 0644 /home/mikheev/.ssh/config
echo 'Host github.com
  IdentityFile /web/matterslash/.ssh/matterslash_rsa_key_for_github' > /home/mikheev/.ssh/config



# Клонируем репу
cd /web/matterslash/
ssh-agent bash -c 'ssh-add /web/matterslash/.ssh/matterslash_rsa_key_for_github; git clone https://github.com/ShashkovS/matterslash.git'
cd /web/matterslash/matterslash
git pull origin master
ssh-agent bash -c 'ssh-add /web/matterslash/.ssh/matterslash_rsa_key_for_github; git pull origin master'















# Ещё раз права
chown -R matterslash:matterslash /web/matterslash/
chmod -R 774 /web/matterslash



# Разрешим nginx'у перезапускать сервис
rm -f /etc/sudoers.d/matterslash
touch /etc/sudoers.d/matterslash
echo '
%nginx ALL= NOPASSWD: /bin/systemctl stop gunicorn.matterslash.socket
%nginx ALL= NOPASSWD: /bin/systemctl start gunicorn.matterslash.socket
%nginx ALL= NOPASSWD: /bin/systemctl restart gunicorn.matterslash.socket
' >> /etc/sudoers.d/matterslash

# Проверка прав на перезапуск, если используется авто-деплой git 
sudo -u nginx /web/matterslash/cgi-bin/pull_and_restart.sh
