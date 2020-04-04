from flask import Flask, jsonify, request, render_template, Response, send_file
import werkzeug.exceptions
import os
import pathlib
import json
from zoomus import ZoomClient

CUR_PATH = pathlib.Path(__file__).parent.absolute()

app = Flask(__name__)

api_key, api_secret, token, channel_name = open('creds.txt').read().splitlines(keepends=False)


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


def list_zoom_lic():
    client = ZoomClient(api_key, api_secret)
    all_users = []
    user_list_response = client.user.list(status='active', page_size=300, page_number=1)
    user_list = json.loads(user_list_response.content)
    all_users.extend(user_list['users'])
    for page_number in range(2, user_list['page_count'] + 1):
        user_list_response = client.user.list(status='active', page_size=300, page_number=page_number)
        user_list = json.loads(user_list_response.content)
        all_users.extend(user_list['users'])

    all_licensed = [f"| {user['last_name']} | {user['first_name']} | {user['email']} |" for user in all_users if user['type'] == 2]
    message = {
        'response_type': 'in_channel',
        'text': '''---\n#### Текущие лицензии zoom\n\n| Фамилия | Имя | Почта   |\n|:--------|:----|:--------|\n'''
                + '\n'.join(all_licensed) + '\n\n---',
    }
    return message


@app.route('/zoom_who', methods=['POST', 'GET'])
def api():
    with open('/web/matterslash/matterslash/log.txt', 'w', encoding='utf-8') as f:
        print('request.form', request.form, file=f)
    if request.form["token"] != token:
        message = {
            'response_type': 'in_channel',
            'text': 'Низзя!'
        }
    elif request.form["channel_name"] != channel_name:
        message = {
            'response_type': 'in_channel',
            'text': 'Этот запрос можно задавать только из канала zoom_licenses :)'
        }
    else:
        message = list_zoom_lic()
    response = jsonify(message)
    response.status_code = 200
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0")
