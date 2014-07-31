from flask import abort, g, make_response, redirect, request, session, url_for
from flask.ext.script import Command
from flask_wtf import Form

from functools import wraps
from markupsafe import Markup

import binascii
import hashlib
import hmac
import json
import os
import redis

from . import reddit
from .app import app


class LogoutForm(Form):
    pass


@app.context_processor
def context():
    def reddit_userlink(username):
        return Markup('<a href="https://ssl.reddit.com/user/%s">/u/%s</a>') % (username, username)

    logout_form = LogoutForm()

    return {'reddit_userlink': reddit_userlink, 'logout_form': logout_form, 'is_admin': is_admin}


@app.route('/logout', methods=('POST',))
def logout():
    form = LogoutForm()
    if form.validate_on_submit():
        for k in list(session.keys()):
            del session[k]
        return redirect('/'), 303
    else:
        return 'Invalid form submission, were you clickjacked?'


def render_flair(text, css_class=None):
    text = text or 'unknown ??'
    if css_class:
        return Markup('<span class="flair flair-%s">%s</span>') % (css_class, text)
    else:
        return Markup('<span class="flair">%s</span>') % text


def mimetype(mimetype_):
    def wrap(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            r = make_response(fn(*a, **kw))
            r.mimetype = mimetype_
            if 'charset' in r.mimetype_params and not mimetype_.startswith('text/'):
                del r.mimetype_params['charset']
            return r
        return wrapper
    return wrap


def require_authorization(*scopes):
    if len(scopes) == 1 and (isinstance(scopes[0], list) or isinstance(scopes[0], set)):
        scopes = scopes[0]
    scopes = set(scopes)
    def wrap(fn):
        @wraps(fn)
        def wrapped(*a, **kw):
            if ('REDDIT_CREDENTIALS' not in session or
                    not set(session['REDDIT_CREDENTIALS']['scope']) >= scopes):
                r = reddit.get()
                return redirect(authorize_url(r, [request.url_rule.endpoint, request.view_args], scopes)), 303
            g.reddit_identity = session['REDDIT_USER']
            return fn(*a, **kw)
        return wrapped
    return wrap


def is_authorized(*scopes):
    if 'REDDIT_CREDENTIALS' not in session:
        return False
    has_scopes = set(session['REDDIT_CREDENTIALS']['scope'])
    return has_scopes >= set(scopes)


def is_admin():
    if 'REDDIT_USER' not in session:
        return False
    return session['REDDIT_USER'] in (app.config['ADMINS'] | reddit.get_moderators())


class AuthCommand(Command):
    "set up OAuth for the moderator account"

    def run(self):
        r = reddit.get()
        p = redis.StrictRedis.from_url(app.config['REDIS_URL']).pubsub()
        p.subscribe('flairbot_oauth')
        print('Click the following link:')
        print(authorize_url(r, ('oauth_dump', {}), reddit.moderator_scopes, refreshable=True))
        for msg in p.listen():
            if msg['type'] == 'subscribe':
                continue
            info = json.loads(msg['data'].decode('utf8'))
            print('Captured OAuth information for /u/{}'.format(info['user']))
            print('Add the following to instance/config.cfg:')
            print('REDDIT_REFRESH_TOKEN = \'{}\''.format(info['creds']['refresh_token']))
            break


def authorize_url(r, state, scope, **kwargs):
    token = binascii.hexlify(os.urandom(16)).decode('ascii')
    state = json.dumps([token, list(state)])
    mac = hmac.new(app.secret_key, state.encode('utf8'), hashlib.sha256).hexdigest()
    return r.get_authorize_url('%s:%s' % (mac, state), scope=list(scope), **kwargs)


@app.route('/oauth_callback')
def oauth_handler():
    r = reddit.get()
    mac, obj = request.args.get('state', '').split(':', 1)
    token, state = json.loads(obj)
    # Check MAC
    mac2 = hmac.new(app.secret_key, obj.encode('utf8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, mac2):
        abort(403)
    # We should be pretty secure here
    code = request.args.get('code', None)
    info = r.get_access_information(code)
    info['scope'] = list(info['scope'])
    user = r.get_me()
    session['REDDIT_USER'] = user.name
    session['REDDIT_VALIDATED_FOR'] = state
    session['REDDIT_CREDENTIALS'] = info
    try:
        returnto = url_for(state[0], **state[1])
    except:
        returnto = url_for('index')
    return redirect(returnto), 303


@app.route('/oauth_dump')
@require_authorization(reddit.moderator_scopes)
def oauth_dump():
    p = redis.StrictRedis.from_url(app.config['REDIS_URL'])
    info = json.dumps({'user': session['REDDIT_USER'],
                       'creds': session['REDDIT_CREDENTIALS']})
    p.publish('flairbot_oauth', info)
    return 'ok'
