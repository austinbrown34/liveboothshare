from flask import g, render_template, redirect, request, session, url_for
import os
import base64
import requests
from requests_toolbelt import MultipartEncoder
import uuid
import logging
from app import app

log = logging.getLogger(__name__)


# @app.route('/share')
# def share_base():
#     # type = content_key.split('.')[-1].upper()
#     return render_template('share.html', content_folder='', content_key='', type='')


@app.route('/share/<content_folder>/<content_key>')
def share(content_folder, content_key):
    type = content_key.split('.')[-1].upper()
    return render_template('share.html', content_folder=content_folder, content_key=content_key, type=type)
