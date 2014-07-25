from flask import abort, g, redirect, request, session, url_for
from flask_wtf import Form

from wtforms.fields import TextField

from . import reddit
from .app import app, db
from .models import Trade


class AcceptTradeForm(Form):
    pass


class CreateTradeForm(Form):
    want_flair = TextField('want_flair', label='Flair you want')
    trade_with = TextField('trade_with', label='Trade with this user only?')


@app.route('/')
def index():
    return 'Nothing to see here...'


@app.route('/t/new', methods=('GET', 'POST'))
def trade_new():
    if 'REDDIT_USER' not in session or session['REDDIT_VALIDATED_FOR'] != ['new']:
        r = reddit.get()
        return redirect(r.get_authorize_url('new', scope=['identity'])), 303
    else:
        return "You are {}".format(session['REDDIT_USER'])


@app.route('/t/accept/<trade_id>')
def trade_accept(trade_id, accept_token=None):
    trade = Trade.by_id(trade_id)
    if trade is None:
        abort(404)
    if 'REDDIT_USER' not in session or session['REDDIT_VALIDATED_FOR'] != ['accept', trade.id]:
        r = reddit.get()
        return redirect(r.get_authorize_url('accept:{}'.format(trade.id), scope=['identity'])), 303
    elif trade.trade_with not in (None, session['REDDIT_USER']):
        return render_template('accept_confirm.html', ok=False, trade=trade)
    else:
        return render_template('accept_confirm.html', ok=True, trade=trade)


@app.route('/oauth_callback')
def oauth_callback():
    r = reddit.get()
    state = request.args.get('state', '').split(':')
    code = request.args.get('code', None)
    info = r.get_access_information(code)
    user = r.get_me()
    session['REDDIT_USER'] = user.name
    session['REDDIT_VALIDATED_FOR'] = state
    if state[0] == 'new':
        return redirect(url_for('trade_new')), 303
    elif state[0] == 'accept':
        return redirect(url_for('trade_accept', trade_id=state[1])), 303

