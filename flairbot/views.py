from flask import abort, flash, g, redirect, render_template, request, session, url_for
from flask_wtf import Form

from wtforms.fields import HiddenField, StringField
from wtforms.validators import Optional, Length, Regexp

from . import reddit, utils
from .app import app, db
from .models import Trade


class ActionTradeForm(Form):
    act_id = HiddenField()
    special_warning = HiddenField()


class CreateTradeForm(Form):
    want_flair = StringField('Flair you want', validators=[Optional(), Length(-1,64)])
    trade_with = StringField('Trade with this user only?', validators=[Optional(), Length(3,20), Regexp(r'^[\w-]+$', message='Illegal characters in name')])
    special_warning = HiddenField()


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
        return redirect(url_for('trade_view', trade_id=existing[0].id)), 303

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
        if flair is None:
            flash("You don't seem to have flair on /r/{}.".format(app.config['REDDIT_SUBREDDIT']), 'alert')
            return render_template('create.html', form=form)

        if flair['flair_css_class'].startswith('special') and form.special_warning.data != 'yes':
            form.special_warning.data = 'yes'
            flash("You currently have a special flair. Remember that all trades are final—it may be very difficult to get back. If you're sure, just click 'Create' again to continue.", 'alert')
            return render_template('create.html', form=form)

        trade = Trade(creator=session['REDDIT_USER'],
                      creator_flair=flair['flair_text'],
                      creator_flair_css=flair['flair_css_class'])
        trade.creator_ip = request.remote_addr

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
            trade.target = target_flair['user']  # case-correct
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


@app.route('/t/<trade_id>/')
@utils.require_authorization('identity', failure_passthrough=True)
def trade_view(trade_id):
    trade = Trade.by_id(trade_id, allow_invalid=True, allow_finished=True, allow_deleted=utils.is_admin())
    if trade is None:
        abort(404)

    form = ActionTradeForm()
    form.act_id.data = trade.id

    ok = True
    you = False
    message = ''

    if trade.deleted:
        ok, message = False, "This trade has been deleted by its creator."
    elif trade.status == 'invalid':
        ok, message = False, "This trade is no longer valid because its creator changed their flair."
    elif trade.status == 'finished':
        ok, message = False, "This trade has already been completed. You can view its details below, \
but it can't be accepted again."

    if ok is False:
        return render_template('trade_view.html', ok=False, you=you, message=message, trade=trade, form=form)

    if g.reddit_identity and trade.target is not None and trade.target != g.reddit_identity:
        ok, message = False, "This trade can only be accepted by /u/{}.".format(trade.target)

    if trade.creator == g.reddit_identity:
        message = "You own this trade. You can cancel it using the button below."
        you = True
        ok = False

    if ok and g.reddit_identity:
        flair = reddit.get_flair(g.reddit_identity)
        if (trade.target_flair not in (None, flair['flair_text']) or
                trade.target_flair_css not in (None, flair['flair_css_class'])):
            ok = False
            message = "Your current flair does not meet the requirements of this trade."
        your_flair = utils.render_flair(flair)
    else:
        your_flair = None

    return render_template('trade_view.html', ok=ok, you=you, your_flair=your_flair, message=message, trade=trade, form=form)


@app.route('/t/<trade_id>/accept', methods=('GET', 'POST'))
@utils.require_authorization('identity')
def trade_accept(trade_id):
    trade = Trade.by_id(trade_id, allow_invalid=True, allow_finished=True)
    if trade is None:
        abort(404)

    form = ActionTradeForm()

    if trade.status != 'valid' or trade.deleted:
        flash("This trade is no longer valid.", 'alert')
        return redirect(url_for('trade_view', trade_id=trade_id)), 303
    elif trade.creator == g.reddit_identity:
        flash("You can't accept your own trade.", 'alert')
        return redirect(url_for('trade_view', trade_id=trade_id)), 303
    elif trade.target is not None and trade.target != g.reddit_identity:
        flash("This trade can only be accepted by /u/{}".format(trade.target), 'alert')
        return redirect(url_for('trade_view', trade_id=trade_id)), 303

    if not form.validate_on_submit():
        return redirect(url_for('trade_view', trade_id=trade_id)), 303
    if form.act_id.data != trade.id:
        abort(400)

    r = reddit.get(moderator=True)

    flair = reddit.get_flair(g.reddit_identity, no_cache=True)
    if flair['flair_text'] == '':
        flash("You don't have flair on /r/{}.", 'alert')
        return redirect(url_for('trade_view', trade_id=trade_id)), 303
    if (trade.target_flair not in (None, flair['flair_text']) or
        trade.target_flair_css not in (None, flair['flair_css_class'])):
        flash("You don't meet the requirements specified by this trade.", 'alert')
        return redirect(url_for('trade_view', trade_id=trade_id)), 303

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
    trade.target_ip = request.remote_addr
    trade.set_status('finished')
    r.set_flair_csv(app.config['REDDIT_SUBREDDIT'], [
        {'user': g.reddit_identity,
         'flair_text': creator_flair['flair_text'],
         'flair_css_class': creator_flair['flair_css_class']},
        {'user': trade.creator,
         'flair_text': flair['flair_text'],
         'flair_css_class': flair['flair_css_class']}])
    db.session.commit()
    creator_flair['user'] = g.reddit_identity
    flair['user'] = trade.creator
    reddit.update_flair_cache(g.reddit_identity, creator_flair)
    reddit.update_flair_cache(trade.creator, flair)
    return render_template('accept_success.html', trade=trade)


@app.route('/t/<trade_id>/delete', methods=('POST',))
@utils.require_authorization('identity')
def trade_delete(trade_id):
    trade = Trade.by_id(trade_id, allow_finished=utils.is_admin(), allow_invalid=utils.is_admin())
    if trade is None:
        abort(404)

    form = ActionTradeForm()

    if form.validate_on_submit() and form.act_id.data == trade.id:
        if g.reddit_identity != trade.creator and not utils.is_admin():
            abort(403)
        trade.deleted = True
        db.session.commit()
        flash('Trade successfully deleted.')
        if utils.is_admin():
            return redirect(url_for('trade_view', trade_id=trade.id)), 303
        else:
            return redirect(url_for('index')), 303

    abort(400)


@app.route('/t/<trade_id>/undelete', methods=('POST',))
@utils.require_authorization('identity')
def trade_undelete(trade_id):
    trade = Trade.by_id(trade_id, allow_finished=True, allow_invalid=True, allow_deleted=True)
    if trade is None or not trade.deleted:
        abort(404)

    form = ActionTradeForm()

    if form.validate_on_submit() and form.act_id.data == trade.id:
        if not utils.is_admin():
            abort(404)
        trade.deleted = False
        db.session.commit()
        flash('Trade successfully undeleted.')
        return redirect(url_for('trade_view', trade_id=trade.id)), 303

    abort(404)


@app.route('/t/<trade_id>/revert', methods=('POST',))
@utils.require_authorization('identity')
def trade_revert(trade_id):
    trade = Trade.by_id(trade_id, allow_finished=True, allow_deleted=True)
    if trade is None or trade.status != 'finished':
        abort(404)

    form = ActionTradeForm()

    if form.validate_on_submit() and form.act_id.data == trade.id:
        if not utils.is_admin():
            abort(404)
        r = reddit.get(moderator=True)
        trade.deleted = True
        trade.set_status('valid')
        target_flair, creator_flair = (
            {'user': trade.target,
             'flair_text': trade.target_flair,
             'flair_css_class': trade.target_flair_css},
            {'user': trade.creator,
             'flair_text': trade.creator_flair,
             'flair_css_class': trade.creator_flair_css})

        r.set_flair_csv(app.config['REDDIT_SUBREDDIT'], [creator_flair, target_flair])
        reddit.update_flair_cache(trade.creator, creator_flair)
        reddit.update_flair_cache(trade.target, target_flair)
        db.session.commit()
        flash('Trade successfully reverted.')
        return redirect(url_for('trade_view', trade_id=trade.id)), 303

    abort(404)


@app.route('/denied/<path:returnto>')
def auth_error(returnto):
    return render_template('auth_error.html', link=utils.script_root() + returnto)


@app.route('/login')
@app.route('/login/<path:returnto>')
@utils.require_authorization('identity')
def login(returnto=None):
    return redirect((utils.script_root() + returnto) if returnto is not None else url_for('index')), 303


@app.route('/logout', methods=('POST',))
@app.route('/logout/<path:returnto>', methods=('POST',))
def logout(returnto=None):
    form = utils.LogoutForm()
    if form.validate_on_submit():
        for k in list(session.keys()):
            del session[k]
        return redirect((utils.script_root() + returnto) if returnto is not None else url_for('index')), 303
    else:
        return 'Invalid form submission, were you clickjacked?'


@app.route('/subreddit.css')
@utils.mimetype('text/css')
def subreddit_css():
    return reddit.get_stylesheet()
