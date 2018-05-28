from flask import Flask
from flask_s3 import FlaskS3

app = Flask(__name__)
app.config['FLASKS3_BUCKET_NAME'] = 'liveboothshare'
s3 = FlaskS3(app)

from app import views
