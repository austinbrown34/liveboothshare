from facebook import get_user_from_cookie, GraphAPI
from flask import g, render_template, redirect, request, session, url_for
import os
import base64
import requests
from requests_toolbelt import MultipartEncoder
import uuid
import logging
from app import app, db
from .models import User

# Facebook app details
FB_APP_ID = '236589033778303'
FB_APP_NAME = 'Live Booth'
FB_APP_SECRET = 'c910225a564fdaa1b825eeed8eea36a6'
log = logging.getLogger(__name__)

def download_file_to_tmp(source_url):
    """
    download `source_url` to /tmp return the full path, doing it in chunks so
    that we don't have to store everything in memory.
    """
    log.debug("download {0}".format(source_url))
    tmp_location = "/tmp/s3_downloads"

    # come up with a random name to avoid clashes.
    rand_name = str(uuid.uuid4().hex.lower()[0:6])

    local_filename = source_url.split('/')[-1]

    # get the extension if it has one
    if local_filename.count(".") > 0:
        ext = local_filename.split('.')[-1]
        tmp_filename = u"{0}.{1}".format(rand_name, ext)
    else:
        tmp_filename = u"{0}.mp4".format(local_filename)

    temp_media_location = os.path.join(tmp_location, tmp_filename)
    # make the temp directory
    if not os.path.exists(tmp_location):
        os.makedirs(tmp_location)

    r = requests.get(source_url, stream=True)
    log.debug("headers = {0}".format(r.headers))
    with open(temp_media_location, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024):
            if chunk:  # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
                os.fsync(f.fileno())
    log.debug("finished download to {0}".format(temp_media_location))
    return temp_media_location


def remove_file(temp_file):
    """ Given a valid file path remove it """
    if os.path.exists(temp_file):
        os.remove(temp_file)


def upload_file(video_url, page_id, poster_url, access_token,
                description, title):
    """
    ``video_url``: this is where the video is in s3.
    ``page_id``:  me or a page_id for the page you want to post too.
    ``poster_url``:  the url to the poster (thumbnail) for this video
    ``access_token``: your facebook access token with permissions to upload
        to the page you want to post too.
    ``description``:  the description of the video you are posting.
    ``title``:  the title of the video you are posting
    """

    # download to data
    local_video_file = download_file_to_tmp(video_url)
    video_file_name = local_video_file.split("/")[-1]

    if video_file_name and video_file_name.count(".") == 0:
        log.debug("video_file_name has no ext {0}".format(video_file_name))
        # if it doesn't have an extension add one to it.
        video_file_name = "{0}.mp4".format(video_file_name)
        log.debug("video_file_name converted to {0}".format(video_file_name))

    # download to data
    local_poster_file = download_file_to_tmp(poster_url)

    # need to encode it.
    with open(local_poster_file, "rb") as image_file:
        poster_encoded_string = base64.b64encode(image_file.read())

    # need binary rep of this, not sure if this would do it

    # put it all together to post to facebook
    if page_id or page_id == 'me':
        path = 'me/videos'
    else:
        path = "{0}/videos".format(page_id)

    fb_url = "https://graph-video.facebook.com/{0}?access_token={1}".format(
             path, access_token)

    log.debug("video_file = {0}".format(local_video_file))
    log.debug("thumb_file = {0}".format(local_poster_file))
    log.debug("start upload to facebook")

    # multipart chunked uploads
    m = MultipartEncoder(
        fields={'description': description,
                'title': title,
                # 'thumb': poster_encoded_string,
                'source': (video_file_name, open(local_video_file, 'rb'))}
    )

    r = requests.post(fb_url, headers={'Content-Type': m.content_type}, data=m)

    if r.status_code == 200:
        j_res = r.json()
        facebook_video_id = j_res.get('id')
        log.debug("facebook_video_id = {0}".format(facebook_video_id))
    else:
        log.error("Facebook upload error: {0}".format(r.text))

    # delete the tmp files
    remove_file(local_video_file)
    remove_file(local_poster_file)

    return facebook_video_id


@app.route('/')
def index():
    # If a user was set in the get_current_user function before the request,
    # the user is logged in.
    if g.user:
        return render_template('index.html', app_id=FB_APP_ID,
                               app_name=FB_APP_NAME, user=g.user)
    # Otherwise, a user is not logged in.
    return render_template('login.html', app_id=FB_APP_ID, name=FB_APP_NAME)


@app.route('/share')
def share():
    if g.user:
        upload_file('https://s3.amazonaws.com/livebooth/uploads/767F69CE-9640-4C38-9C69-B6CA84686300.mov', 'me', 'http://livebooth.xyz/img/phone-black.png', g.user['access_token'],
                    "Live Booth", "Live Booth")
        return render_template('index.html', app_id=FB_APP_ID,
                               app_name=FB_APP_NAME, user=g.user)
    # Otherwise, a user is not logged in.
    return render_template('login.html', app_id=FB_APP_ID, name=FB_APP_NAME)

@app.route('/logout')
def logout():
    """Log out the user from the application.

    Log out the user from the application by removing them from the
    session.  Note: this does not log the user out of Facebook - this is done
    by the JavaScript SDK.
    """
    session.pop('user', None)
    return redirect(url_for('index'))


@app.before_request
def get_current_user():
    """Set g.user to the currently logged in user.

    Called before each request, get_current_user sets the global g.user
    variable to the currently logged in user.  A currently logged in user is
    determined by seeing if it exists in Flask's session dictionary.

    If it is the first time the user is logging into this application it will
    create the user and insert it into the database.  If the user is not logged
    in, None will be set to g.user.
    """

    # Set the user in the session dictionary as a global g.user and bail out
    # of this function early.
    if session.get('user'):
        g.user = session.get('user')
        return

    # Attempt to get the short term access token for the current user.
    result = get_user_from_cookie(cookies=request.cookies, app_id=FB_APP_ID,
                                  app_secret=FB_APP_SECRET)

    # If there is no result, we assume the user is not logged in.
    if result:
        # Check to see if this user is already in our database.
        user = User.query.filter(User.id == result['uid']).first()

        if not user:
            # Not an existing user so get info
            graph = GraphAPI(result['access_token'])
            profile = graph.get_object('me')
            if 'link' not in profile:
                profile['link'] = ""

            # Create the user and insert it into the database
            user = User(id=str(profile['id']), name=profile['name'],
                        profile_url=profile['link'],
                        access_token=result['access_token'])
            db.session.add(user)
        elif user.access_token != result['access_token']:
            # If an existing user, update the access token
            user.access_token = result['access_token']

        # Add the user to the current session
        session['user'] = dict(name=user.name, profile_url=user.profile_url,
                               id=user.id, access_token=user.access_token)

    # Commit changes to the database and set the user as a global g.user
    db.session.commit()
    g.user = session.get('user', None)
