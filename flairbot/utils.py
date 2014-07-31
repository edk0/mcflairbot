from flask import abort, g, make_response, redirect, request, session, url_for
from flask_wtf import Form

from functools import wraps
from markupsafe import Markup

import binascii
import hashlib
import hmac
import json
import os

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


def authorize_url(r, state, scope, **kwargs):
    token = binascii.hexlify(os.urandom(16)).decode('ascii')
    state = json.dumps([token, list(state)])
    session['AUTHORIZE_TOKEN'] = token
    mac = hmac.new(app.secret_key, state.encode('utf8'), hashlib.sha256).hexdigest()
    return r.get_authorize_url('%s:%s' % (mac, state), scope=list(scope), **kwargs)


@app.route('/oauth_callback')
def oauth_handler():
    r = reddit.get()
    mac, obj = request.args.get('state', '').split(':', 1)
    token, state = json.loads(obj)
    # Check token
    if session.get('AUTHORIZE_TOKEN') != token:
        if 'AUTHORIZE_TOKEN' in session:
            del session['AUTHORIZE_TOKEN']
        abort(403)
    del session['AUTHORIZE_TOKEN']
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
