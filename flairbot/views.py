from flask import abort, flash, g, redirect, render_template, request, session, url_for
from flask_wtf import Form

from wtforms.fields import HiddenField, StringField
from wtforms.validators import Optional, Length, Regexp

from . import reddit, utils
from .app import app, db
from .models import Trade


class AcceptTradeForm(Form):
    accept_id = HiddenField()


class CreateTradeForm(Form):
    want_flair = StringField('Flair you want', validators=[Optional(), Length(-1,64)])
    trade_with = StringField('Trade with this user only?', validators=[Optional(), Length(3,20), Regexp(r'^[\w-]+$', message='Illegal characters in name')])


class DeleteTradeForm(Form):
    delete_id = HiddenField()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/t/new/', methods=('GET', 'POST'))
@utils.require_authorization('identity')
def trade_new():
    form = CreateTradeForm()

    existing = (Trade.query_valid()
            .filter(Trade.creator == session['REDDIT_USER'])
            .limit(1)
            .all())

    if len(existing) > 0:
        flash('You already have a trade open. If you wish to make a different trade, delete it first.', 'alert')
        return redirect(url_for('trade_accept', trade_id=existing[0].id)), 303

    if form.validate_on_submit():
        if form.trade_with.data != '' and form.want_flair.data != '':
            form.want_flair.data = ''
            form.errors['want_flair'] = [
                "Leave this blank if you're trading with a specific user—their flair will be retrieved automatically."]
            return render_template('create.html', form=form)
        if form.trade_with.data.lower() == g.reddit_identity.lower():
            form.errors['trade_with'] = ["You can't trade flair with yourself."]
            return render_template('create.html', form=form)

        user = session['REDDIT_USER']
        flair = reddit.get_flair(user)
        trade = Trade(creator=session['REDDIT_USER'],
                      creator_flair=flair['flair_text'],
                      creator_flair_css=flair['flair_css_class'])

        if form.trade_with.data != '':
            target = form.trade_with.data
            target_flair = reddit.get_flair(target)
            if target_flair is None:
                form.errors['trade_with'] = ["That user doesn't seem to exist."]
                return render_template('create.html', form=form)
            if target_flair['flair_text'] == '':
                form.errors['trade_with'] = [
                        "That user doesn't have flair on /r/{}.".format(app.config['REDDIT_SUBREDDIT'])]
                return render_template('create.html', form=form)
            trade.target = target
            trade.target_flair = target_flair['flair_text']
            trade.target_flair_css = target_flair['flair_css_class']
        elif form.want_flair.data != '':
            trade.target_flair = form.want_flair.data
        else:
            flash('Please fill in exactly one of the text boxes to set up your trade.', 'alert')
            return render_template('create.html', form=form)
        db.session.add(trade)
        db.session.commit()
        return render_template('created.html', trade=trade)

    return render_template('create.html', form=form)


@app.route('/t/<trade_id>/', methods=('GET', 'POST'))
@utils.require_authorization('identity')
def trade_accept(trade_id):
    trade = Trade.by_id(trade_id, allow_invalid=True, allow_finished=True)
    if trade is None:
        abort(404)

    accept_form = AcceptTradeForm(); accept_form.accept_id.data = trade.id
    delete_form = DeleteTradeForm(); delete_form.delete_id.data = trade.id

    def display(ok=False, you=False, **kw):
        return render_template('accept_confirm.html', ok=ok, you=you, trade=trade,
                                accept_form=accept_form, delete_form=delete_form, **kw)

    if trade.status in ('finished', 'invalid'):
        return display(ok=False)
    elif trade.creator == g.reddit_identity:
        return display(you=True)
    elif trade.target not in (None, session['REDDIT_USER']):
        return display(ok=False)
    else:
        r = reddit.get(moderator=True)
        flair = reddit.get_flair(g.reddit_identity, no_cache=True)
        if flair['flair_text'] == '':
            return display(ok=False)
        if (trade.target_flair not in (None, flair['flair_text']) or
            trade.target_flair_css not in (None, flair['flair_css_class'])):
            return display(ok=False)
        if accept_form.validate_on_submit():
            # make sure ids match
            if accept_form.accept_id.data != trade.id:
                abort(400)
            # one extra thing: check the creator's flair matches what we saved
            creator_flair = reddit.get_flair(trade.creator, no_cache=True)
            if (creator_flair['flair_text'] != trade.creator_flair or
                    creator_flair['flair_css_class'] != trade.creator_flair_css):
                trade.set_status('invalid')
                db.session.commit()
                return display(ok=False)
            # actually make the trade
            trade.target = g.reddit_identity
            trade.target_flair = flair['flair_text']
            trade.target_flair_css = flair['flair_css_class']
            trade.set_status('finished')
            db.session.commit()
            r.set_flair_csv(app.config['REDDIT_SUBREDDIT'], [
                {'user': g.reddit_identity,
                 'flair_text': trade.creator_flair,
                 'flair_css_class': trade.creator_flair_css},
                {'user': trade.creator,
                 'flair_text': flair['flair_text'],
                 'flair_css_class': flair['flair_css_class']}])
            return render_template('accept_success.html', trade=trade)
        else:
            your_flair = utils.render_flair(flair['flair_text'], flair['flair_css_class'])
            return display(ok=True, your_flair=your_flair)


@app.route('/t/<trade_id>/delete', methods=('POST',))
@utils.require_authorization('identity')
def trade_delete(trade_id):
    trade = Trade.by_id(trade_id)
    if trade is None:
        abort(404)

    delete_form = DeleteTradeForm()

    if delete_form.validate_on_submit() and delete_form.delete_id.data == trade.id:
        if g.reddit_identity != trade.creator and util.is_admin():
            abort(403)
        trade.set_status('deleted')
        db.session.commit()
        flash('Trade successfully deleted')
        return redirect(url_for('index')), 303

    abort(400)


@app.route('/subreddit.css')
@utils.mimetype('text/css')
def subreddit_css():
    return reddit.get_stylesheet()


@app.route('/system/authme/')
@utils.require_authorization('identity')
def authme():
    r = reddit.get()
    if g.reddit_identity not in app.config['ADMINS']:
        session['AUTHME_STEP'] = 'begin'
        return redirect(util.authorize_url(r, ('authme',), {'identity'}))
    elif session.get('AUTHME_STEP') == 'logout_warning':
        return redirect(_authorize(r, ['authme_complete'], list(reddit.moderator_scopes), refreshable=True))
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
