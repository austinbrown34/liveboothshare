from flask import g, render_template, redirect, request, session, url_for, send_file, jsonify
import os
import base64
import requests
from requests_toolbelt import MultipartEncoder
import uuid
import logging
from app import app
import boto3
import botocore

log = logging.getLogger(__name__)


# @app.route('/share')
# def share_base():
#     # type = content_key.split('.')[-1].upper()
#     return render_template('share.html', content_folder='', content_key='', type='')
# https://khr9zw6byi.execute-api.us-west-2.amazonaws.com/dev/v1/convert



@app.route('/convert', methods=['POST'])
def convert():
    # data = request.json
    email =request.form['email']
    url = request.form['url']
    # endpoint = url.split('https://s3.amazonaws.com/livebooth/')[1]
    status = ''
    with requests.Session() as session:
        r = session.post('https://khr9zw6byi.execute-api.us-west-2.amazonaws.com/dev/v1/convert', json={"url": url, "email": email}, verify=False)
        status = r.status_code
    # r = requests.post('https://khr9zw6byi.execute-api.us-west-2.amazonaws.com/dev/v1/convert', json={"url": url, "email": email})
    # return redirect(url_for('share/{}'.format(endpoint)))
    return redirect('/dev/share/{}'.format(url), code=302)


@app.route('/download/<content_folder>/<content_key>')
def download(content_folder, content_key):
    print("about to download")
    try:
        print("about to s3")
        s3 = boto3.resource('s3')
        print ("s3!")

        try:
            print("about to bucket")
            try:
                os.remove('/tmp/{}'.format(content_key))
            except OSError:
                pass
            s3.Bucket('livebooth').download_file(content_folder + '/' + content_key, '/tmp/{}'.format(content_key))
            print(os.listdir('/tmp'))
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("The object does not exist.")
            else:
                print(e.response['Error']['Code'])
        # r = requests.get('https://s3.amazonaws.com/livebooth/' + content_folder + '/' + content_key)

        return send_file('/tmp/{}'.format(content_key), attachment_filename=content_key, as_attachment=True)
    except Exception as e:
        return str(e)
    # type = content_key.split('.')[-1].upper()
    # return render_template('share.html', content_folder=content_folder, content_key=content_key, type=type)


@app.route('/share/<content_folder>/<content_key>')
def share(content_folder, content_key):
    print("in share!")
    type = content_key.split('.')[-1].upper()
    return render_template('share.html', content_folder=content_folder, content_key=content_key, type=type)
