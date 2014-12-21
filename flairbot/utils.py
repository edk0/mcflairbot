from flask import abort, g, has_request_context, make_response, redirect, request, session, url_for
from flask.ext.script import Command
from flask_wtf import Form

from collections import Counter
from functools import wraps
from markupsafe import Markup

from sqlalchemy import and_, or_

import binascii
import csv
import datetime
import hashlib
import hmac
import json
import os
import praw
import redis
import time

from . import reddit
from .app import app


class LogoutForm(Form):
    pass


@app.context_processor
def context():
    def reddit_userlink(username):
        return Markup('<a href="https://pay.reddit.com/user/%s">/u/%s</a>') % (username, username)

    def login_url():
        if request.path == '/':
            return url_for('login')
        return url_for('login', returnto=request.path[1:])

    def logout_url():
        if request.path == '/':
            return url_for('logout')
        return url_for('logout', returnto=request.path[1:])

    logout_form = LogoutForm()

    return {'reddit_userlink': reddit_userlink,
            'logout_form': logout_form,
            'login_url': login_url,
            'logout_url': logout_url,
            'is_admin': is_admin}


def script_root():
    return request.script_root + '/'


def render_flair(text, css_class=None):
    if isinstance(text, dict):
        css_class = text.get('flair_css_class', None)
        text = text.get('flair_text', None)
    text = text or 'unknown'
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


def require_authorization(*scopes, **kw):
    if len(scopes) == 1 and (isinstance(scopes[0], list) or isinstance(scopes[0], set)):
        scopes = scopes[0]
    scopes = set(scopes)
    failure_passthrough = kw.get('failure_passthrough', False)
    def wrap(fn):
        @wraps(fn)
        def wrapped(*a, **kw):
            if 'REDDIT_CREDENTIALS' in session:
                g.reddit_scopes = set(session['REDDIT_CREDENTIALS']['scope'])
            if ('REDDIT_CREDENTIALS' not in session or
                    not g.reddit_scopes >= scopes):
                if failure_passthrough:
                    g.reddit_identity = False
                    return fn(*a, **kw)
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
    remote_addr = '*'
    if has_request_context() and request.remote_addr is not None:
        remote_addr = request.remote_addr
    state = json.dumps([token, time.time(), remote_addr, list(state)])
    mac = hmac.new(app.secret_key, state.encode('utf8'), hashlib.sha256).hexdigest()
    return r.get_authorize_url('%s:%s' % (mac, state), scope=list(scope), **kwargs)


@app.route('/oauth_callback')
def oauth_handler():
    r = reddit.get()
    mac, obj = request.args.get('state', '').split(':', 1)
    token, timestamp, addr, state = json.loads(obj)
    # Check MAC
    mac2 = hmac.new(app.secret_key, obj.encode('utf8'), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(mac, mac2):
        abort(403)
    # Check time and IP
    if time.time() > timestamp + app.config['AUTHORIZATION_EXPIRY']:
        abort(403)
    if addr != '*' and request.remote_addr != addr:
        abort(403)
    if request.args.get('error') == 'access_denied':
        adapter = app.create_url_adapter(request)
        adapter.script_name = '/'
        returnto = adapter.build(state[0], values=state[1])[1:]
        return redirect(url_for('auth_error', returnto=returnto)), 303
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
@require_authorization(reddit.moderator_scopes, failure_passthrough=True)
def oauth_dump():
    if g.reddit_identity is False:
        return "you are not logged in or your authorization is not sufficient \
to run the app. please run `python manage.py setup-auth` from the server \
instance to get here."
    elif g.reddit_identity not in reddit.get_moderators():
        return "this account, {}, does not moderate /r/{}. please repeat the \
process with another account.".format(g.reddit_identity, app.config['REDDIT_SUBREDDIT'])
    p = redis.StrictRedis.from_url(app.config['REDIS_URL'])
    info = json.dumps({'user': session['REDDIT_USER'],
                       'creds': session['REDDIT_CREDENTIALS']})
    p.publish('flairbot_oauth', info)
    return "authorization successful, check console"

@praw.decorators.restrict_access('flair')
def get_flair_selector(r, subreddit):
    r.config.API_PATHS['flairselector'] = 'r/%s/api/flairselector'
    return r.request_json(r.config['flairselector'] % subreddit, data=True)

class StatsCommand(Command):
    """compute flair stats"""

    def run(self):
        from .models import Trade
        r = reddit.get(moderator=True)
        active = Counter()
        authors = set()
        stop = time.time() - 2592000
        dstop = datetime.datetime.utcfromtimestamp(stop)
        print('# reading submissions')
        n = 0
        m = 0
        for s in r.get_subreddit(app.config['REDDIT_SUBREDDIT']).get_new(limit=None):
            if s.created_utc < stop:
                break
            n += 1
            s.replace_more_comments(limit=None, threshold=0)
            flat = praw.helpers.flatten_tree(s.comments)
            for c in flat:
                m += 1
                if c.author is None:
                    continue
                if c.author.name in authors:
                    continue
                authors.add(c.author.name)
                active[(c.author_flair_text, c.author_flair_css_class)] += 1
            if s.author.name in authors:
                continue
            authors.add(s.author.name)
            active[(s.author_flair_text, s.author_flair_css_class)] += 1
        print('({} submissions, {} comments)'.format(n, m))
        print('# reading flair selector')
        r = reddit.get(moderator=True)
        selector = get_flair_selector(r, app.config['REDDIT_SUBREDDIT'])
        available = set()
        for f in selector['choices']:
            available.add((f['flair_text'], f['flair_css_class'][6:]))
        frequency = Counter()
        print('# reading user flair list')
        r = reddit.get(moderator=True)
        for flair in r.get_flair_list(app.config['REDDIT_SUBREDDIT'], limit=None):
            frequency[(flair['flair_text'], flair['flair_css_class'])] += 1
        print("# smokin' and writin'")
        with open('stats.csv', 'w') as f:
            wr = csv.writer(f)
            wr.writerow(['flair text', 'css class', 'enabled', 'total count', 'active count', 'trade activity'])
            for flair in sorted(frequency.keys(), key=lambda k: (-frequency[k], k[0])):
                if flair[0] is None or flair[1] is None or flair[0] == '':
                    continue
                at = Trade.query\
                    .filter(
                        Trade.status == 'finished',
                        Trade.finalized > stop,
                        or_(
                            and_(Trade.creator_flair == flair[0],
                                 Trade.creator_flair_css == flair[1]),
                            and_(Trade.target_flair == flair[0],
                                 Trade.target_flair_css == flair[1])))\
                    .count()
                av = 'YES' if flair in available else 'NO'
                wr.writerow([flair[0], flair[1], av, frequency[flair], active[flair], at])
