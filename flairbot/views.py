from flask import abort, g, redirect, render_template, request, session, url_for
from flask_wtf import Form

from wtforms.fields import StringField
from wtforms.validators import Length, Regexp

import binascii
import os

from . import reddit
from .app import app, db
from .models import Trade


class AcceptTradeForm(Form):
    pass


class CreateTradeForm(Form):
    want_flair = StringField('Flair you want', validators=[Length(-1,64)])
    trade_with = StringField('Trade with this user only?', validators=[Length(3,20), Regexp(r'^[\w-]+$')])


@app.route('/')
def index():
    return 'Nothing to see here...'


@app.route('/t/new', methods=('GET', 'POST'))
def trade_new():
    form = CreateTradeForm()
    if 'REDDIT_USER' not in session or session.get('REDDIT_VALIDATED_FOR') != ['new']:
        r = reddit.get()
        return redirect(_authorize(r, ['new'], ['identity'])), 303
    elif form.validate_on_submit():
        r = reddit.get(moderator=True)
        user = session['REDDIT_USER']
        flair = r.get_flair(app.config['REDDIT_SUBREDDIT'], user)
        trade = Trade(creator=session['REDDIT_USER'], creator_flair=flair)
        db.session.add(trade)
        db.session.commit()
        return render_template('created.html', trade=trade)
    else:
        return render_template('create.html', form=form)


@app.route('/t/accept/<trade_id>')
def trade_accept(trade_id, accept_token=None):
    trade = Trade.by_id(trade_id)
    if trade is None:
        abort(404)
    if 'REDDIT_USER' not in session or session['REDDIT_VALIDATED_FOR'] != ['accept', trade.id]:
        r = reddit.get()
        return redirect(_authorize(r, ['accept', trade.id], ['identity'])), 303
    elif trade.trade_with not in (None, session['REDDIT_USER']):
        return render_template('accept_confirm.html', ok=False, trade=trade)
    else:
        return render_template('accept_confirm.html', ok=True, trade=trade)


@app.route('/subreddit.css')
def subreddit_css():
    return reddit.get_stylesheet()


@app.route('/system/authme')
def authme():
    r = reddit.get()
    if (session.get('REDDIT_USER') not in app.config['ADMINS'] or
        session.get('REDDIT_VALIDATED_FOR') != ['authme']):
        session['AUTHME_STEP'] = 'begin'
        return redirect(_authorize(r, ['authme'], ['identity']))
    elif session.get('AUTHME_STEP') == 'logout_warning':
        session['AUTHME_STEP'] = 'login_as_moderator'
        return redirect(_authorize(r, ['authme_complete'], ['identity', 'flair', 'modflair', 'mysubreddits'], refreshable=True))
    else:
        session['AUTHME_STEP'] = 'logout_warning'
        return '''Log out of Reddit, then back in again as the bot account.<br/>
<br/>
<a href="">When you've done that, click here.</a>'''


@app.route('/system/authme/complete')
def authme_complete():
    r = reddit.get(user_from_session=True)
    if 'REDDIT_USER' in session and session['REDDIT_VALIDATED_FOR'] == ['authme_complete']:
        del session['AUTHME_STEP']
        subreddits = [sub.display_name for sub in r.get_my_moderation()]
        if app.config['REDDIT_SUBREDDIT'] not in subreddits:
            return 'You do not moderate /r/{}!'.format(app.config['REDDIT_SUBREDDIT'])
        return '''OAuth2 information captured for {user}.<br/>
<br/>
You moderate: {subs}<br/>
<br/>
Add the following to /instance/config.cfg:<br/>
<pre>REDDIT_REFRESH_TOKEN = '{creds[refresh_token]}'</pre>'''.format(
            user=session['REDDIT_USER'],
            subs=subreddits,
            creds=session['REDDIT_CREDENTIALS'])


def _authorize(r, state, scope, **kwargs):
    token = binascii.hexlify(os.urandom(16)).decode('ascii')
    state = ':'.join([token] + state)
    session['AUTHORIZE_TOKEN'] = token
    return r.get_authorize_url(state, scope=scope, **kwargs)


@app.route('/oauth_callback')
def oauth_callback():
    r = reddit.get()
    state = request.args.get('state', '').split(':')
    if session.get('AUTHORIZE_TOKEN') != state.pop(0):
        if 'AUTHORIZE_TOKEN' in session:
            del session['AUTHORIZE_TOKEN']
        abort(403)
    del session['AUTHORIZE_TOKEN']
    code = request.args.get('code', None)
    info = r.get_access_information(code)
    info['scope'] = list(info['scope'])
    user = r.get_me()
    session['REDDIT_USER'] = user.name
    session['REDDIT_VALIDATED_FOR'] = state
    session['REDDIT_CREDENTIALS'] = info
    if state[0] == 'new':
        return redirect(url_for('trade_new')), 303
    elif state[0] == 'accept':
        return redirect(url_for('trade_accept', trade_id=state[1])), 303
    elif state[0] == 'authme':
        return redirect(url_for('authme')), 303
    elif state[0] == 'authme_complete':
        return redirect(url_for('authme_complete')), 303

