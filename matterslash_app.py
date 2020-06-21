from flask import Flask, jsonify, request, render_template, Response, send_file
import werkzeug.exceptions
import pathlib
import json
import requests
import time
import jwt
import os

CUR_PATH = pathlib.Path(__file__).parent.absolute()
os.chdir(CUR_PATH)

app = Flask(__name__)

api_key, api_secret, token_who, token_lic = open('creds.txt').read().splitlines(keepends=False)


def simplify_name(name):
    return name.strip().lower().replace('ё', 'е').replace('-', '').replace(' ', '').replace('\t', '')


try:
    teachers = open('teachers.txt', 'r', encoding='utf-8').read().splitlines()
except:
    teachers = []
for i, row in enumerate(teachers):
    fio, _, m = row.rpartition('\t')
    teachers[i] = (simplify_name(fio), m)

email_to_user_id = {}

ZOOM_WHO = '''\
#### Текущие лицензии zoom

| Фамилия | Имя | Почта   |
|:--------|:----|:--------|
{}
'''

MOVE_LIC_FROM_TO = '''\
##### Лицензия zoom успешно перенесена от {} к {}.
'''

GIVE_LIC_TO = '''\
##### Лицензия zoom успешно выдана {}.
'''

USER_NOT_FOUND = '''\
##### Пользователь {} не найден в zoom. Укажите правильный email.
'''

UNKNOWN_ERROR = '''\
##### Произошла какая-то ошибка. Пусть Шашков разбирается :(
Вот ему в помощь: ```{}```
'''

NO_LIC = '''\
#####  Хм. Возможно, у {} не было лицензии или email введён неправильно. Не удалось накинуть лицензию {}.
Zoom ответил, что «`{}`».
Попобуйте выполнить `/zoom_who`, чтобы узнать, у кого лицензия.
Посмотрите [вот в этой гугль-табличке](https://docs.google.com/spreadsheets/d/1XrHuXyzJxUgsRNfgQD5ALy4VmtWt9LzTBsc17WLrZxA/edit#gid=0), кому она сейчас не нужна.
'''


# This is just a test route. It is autotested after deploy
@app.route('/test_app_is_working_kQK74RxmgPPm69')
def test_app_is_working():
    return "Yup! The app is working!\n"


@app.errorhandler(werkzeug.exceptions.BadRequest)
def bad_request_error_handler(e=None):
    message = {
        'status': 400,
        'message': 'Bad request or API method not found: ' + request.url,
        'return': {'debug': str(e)}
    }
    response = jsonify(message)
    response.status_code = 400
    return response


@app.errorhandler(werkzeug.exceptions.InternalServerError)
def internal_error_handler(e=None):
    message = {
        'status': 500,
        'message': 'Internal server error: ' + request.url,
        'return': {'debug': str(e)}
    }
    response = jsonify(message)
    response.status_code = 500
    return response


def generate_jwt_header():
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"iss": api_key, "exp": int(time.time() + 60)}
    token = jwt.encode(payload, api_secret, algorithm="HS256", headers=header)
    return {"Authorization": "Bearer {}".format(token.decode("utf-8"))}


def update_email_cache(all_users):
    global email_to_user_id
    email_to_user_id.clear()
    for user in all_users:
        email_to_user_id[user['email'].strip().lower()] = user['id']


def list_zoom_users(url="https://api.zoom.us/v2/users"):
    headers = generate_jwt_header()
    all_users = []
    user_list_response = requests.request("GET", url, headers=headers, params=dict(status='active', page_size=300, page_number=1))
    user_list = json.loads(user_list_response.content)
    all_users.extend(user_list['users'])
    for page_number in range(2, user_list['page_count'] + 1):
        user_list_response = requests.request("GET", url, headers=headers, params=dict(status='active', page_size=300, page_number=page_number))
        user_list = json.loads(user_list_response.content)
        all_users.extend(user_list['users'])
    update_email_cache(all_users)
    return all_users


def format_licenced_user(all_users):
    all_licensed = [f"| {user['last_name']} | {user['first_name']} | `{user['email']}` |" for user in all_users if user['type'] == 2]
    message = {
        'response_type': 'in_channel',
        'text': ZOOM_WHO.format('\n'.join(all_licensed))
    }
    return message


def move_lic(frm: str, to: str) -> dict:
    # См. https://marketplace.zoom.us/docs/api-reference/zoom-api/users/userupdate
    frm = frm.strip().lower()
    to = to.strip().lower()
    cache_updated = False
    if to not in email_to_user_id:
        list_zoom_users()
        cache_updated = True
        if to not in email_to_user_id:
            return {
                'response_type': 'in_channel',
                'text': USER_NOT_FOUND.format(to)
            }
    to_id = email_to_user_id[to]

    headers = generate_jwt_header()
    headers['content-type'] = 'application/json'
    url_to = f"https://api.zoom.us/v2/users/{to_id}"
    querystring = {"login_type": "100"}
    payload_to = json.dumps({"type": 2})
    # Сначала проверим, вдруг лицензии пустуют
    for tries in (1, 2):
        response_to = requests.request("PATCH", url_to, data=payload_to, headers=headers, params=querystring)
        print('response_to', response_to, response_to.text)
        if response_to.status_code == 204 and tries == 1:
            return {
                'response_type': 'in_channel',
                'text': GIVE_LIC_TO.format(to)
            }
        elif response_to.status_code == 204 and tries == 2:
            return {
                'response_type': 'in_channel',
                'text': MOVE_LIC_FROM_TO.format(frm, to)
            }
        elif response_to.status_code == 404:
            return {
                'response_type': 'in_channel',
                'text': USER_NOT_FOUND.format(to)
            }
        elif response_to.status_code == 400 and response_to.json()['code'] in (200, 3412) and tries == 1:
            if frm not in email_to_user_id and not cache_updated:
                list_zoom_users()
            if frm not in email_to_user_id:
                return {
                    'response_type': 'in_channel',
                    'text': USER_NOT_FOUND.format(frm)
                }
            frm_id = email_to_user_id[frm]
            url_frm = f"https://api.zoom.us/v2/users/{frm_id}"
            payload_frm = json.dumps({"type": 1})
            response_frm = requests.request("PATCH", url_frm, data=payload_frm, headers=headers, params=querystring)
            print('response_frm', response_frm, response_frm.text)
        elif response_to.status_code == 400 and response_to.json()['code'] in (200, 3412) and tries == 2:
            return {
                'response_type': 'in_channel',
                'text': NO_LIC.format(frm, to, response_to.text)
            }
        else:
            return {
                'response_type': 'in_channel',
                'text': UNKNOWN_ERROR.format(response_to.text)
            }


def list_zoom_lic():
    all_users = list_zoom_users()
    return format_licenced_user(all_users)


@app.route('/zoom_who', methods=['POST', 'GET'])
def zoom_who_api():
    # with open('/web/matterslash/matterslash/log.txt', 'w', encoding='utf-8') as f:
    #     print('request.form', request.form, file=f)
    if request.form["token"] != token_who:
        message = {
            'response_type': 'in_channel',
            'text': 'Низзя!'
        }
    # elif request.form["channel_name"] != 'zoom_licenses':
    #     message = {
    #         'response_type': 'in_channel',
    #         'text': 'Этот запрос можно задавать только из канала zoom_licenses :)'
    #     }
    else:
        message = list_zoom_lic()
    response = jsonify(message)
    response.status_code = 200
    return response


def move_with_given_parms(parms):
    if len(parms) != 2:
        return {
            'response_type': 'in_channel',
            'text': 'Напишите запрос в виде `/zoom_lic [от_кого] [кому]`, например, `/zoom_lic шашков кириенко` или `/zoom_lic shashkov@179.ru dk@179.ru`'
        }
    for i, addr in enumerate(parms):
        if '@' not in addr:
            addr_n = simplify_name(addr)
            tst = [email for fio, email in teachers if fio.startswith(addr_n)]
            if len(tst) == 1:
                parms[i] = tst[0]
            else:
                return {
                    'response_type': 'in_channel',
                    'text': 'Напишите запрос в виде `/zoom_lic [от_кого] [кому]`, например, `/zoom_lic шашков кириенко` или `/zoom_lic shashkov@179.ru dk@179.ru`. Сейчас по {} не получилось определить человека.'.format(
                        addr)
                }
    frm, to = parms
    return move_lic(frm, to)


def move_zoom_lic(request):
    if request.form["token"] != token_lic:
        return {
            'response_type': 'in_channel',
            'text': 'Низзя!'
        }
    elif request.form["channel_name"] != 'zoom_licenses':
        return {
            'response_type': 'in_channel',
            'text': 'Этот запрос можно задавать только из канала zoom_licenses :)'
        }
    parms = request.form["text"].split()
    return move_with_given_parms(parms)


@app.route('/zoom_lic', methods=['POST', 'GET'])
def zoom_lic_api():
    message = move_zoom_lic(request)
    response = jsonify(message)
    response.status_code = 200
    return response


if __name__ == "__main__":
    # app.run(host="0.0.0.0")
    move_with_given_parms(['кири', 'шаш'])