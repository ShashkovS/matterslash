#!/bin/bash
repo_path=/web/matterslash/matterslash

echo 'Обновляем код с githubа'
cd $repo_path
git reset --hard HEAD && git pull origin master

echo 'Переходим в venv'
source ../matterslash_env/bin/activate

echo 'Ставим библиотеки'
pip install -r requirements.txt

# echo 'Стопим gunicorn'
# systemctl stop gunicorn.matterslash.socket

echo 'Перезапускаем всё'
# systemctl daemon-reload
sudo /bin/systemctl restart gunicorn.matterslash.socket
# # Проверяем корректность конфига
# nginx -t
# # Перезапускаем nginx
# systemctl reload nginx.service

echo 'Тестируем: дёргаем сокет локально'
echo
curl -sS --unix-socket /web/matterslash/matterslash.socket http://localhost/test_app_is_working_kQK74RxmgPPm69 | head -n 5
echo

echo 'Тестируем: дёргаем приложение через вебсервис'
echo
curl -sS https://matterslash.proj179.ru/test_app_is_working_kQK74RxmgPPm69 | head -n 5
echo
