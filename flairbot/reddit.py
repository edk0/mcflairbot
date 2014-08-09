from flask import session

import cssutils
import cssutils.css
import praw
import requests
import time

from .app import app, cache

logger = app.logger.getChild('reddit')

moderator_scopes = {'identity', 'mysubreddits', 'modflair', 'flair'}

_access_expiry = -1
_access_info = None


def get(user_from_session=False, moderator=False, refresh_token=None):
    global _access_info, _access_expiry

    r = praw.Reddit('/u/mindcrack_flair_bot, by /u/edk141', disable_update_check=True)
    r.set_oauth_app_info(app.config['REDDIT_CLIENT_ID'],
                         app.config['REDDIT_CLIENT_SECRET'],
                         app.config['REDDIT_REDIRECT_URI'])
    if user_from_session:
        credentials = session['REDDIT_CREDENTIALS']
        r.set_access_credentials(set(credentials['scope']),
                                 credentials['access_token'],
                                 credentials['refresh_token'])
    elif moderator:
        if _access_info is not None and _access_expiry > time.time():
            r.set_access_credentials(moderator_scopes, *_access_info)
        else:
            if refresh_token is None:
                refresh_token = app.config['REDDIT_REFRESH_TOKEN']
            info = r.refresh_access_information(refresh_token)
            _access_info = (info['access_token'], info['refresh_token'])
            _access_expiry = time.time() + 3300  # give ourselves a 5-minute margin
    return r


@cache.cached(timeout=app.config['CACHE_TIME_LONG'], key_prefix='reddit_stylesheet_cache')
def get_stylesheet():
    tries = 3
    while tries > 0:
        time.sleep(3)
        r = requests.get('http://www.reddit.com/r/{}/stylesheet.css'.format(
                app.config.get('STYLE_SUBREDDIT', app.config['REDDIT_SUBREDDIT'])))
        if r.status_code == 200:
            break
        tries -= 1
    sheet = cssutils.parseString(r.text)
    new = cssutils.css.CSSStyleSheet()
    for rule in sheet.cssRules.rulesOfType(cssutils.css.CSSRule.STYLE_RULE):
        for selector in rule.selectorList:
            if selector.selectorText == 'content':
                selector.selectorText = '.flair'
            if selector.selectorText.startswith('.flair'):
                new.add(rule)
    return new.cssText


@cache.memoize(timeout=app.config['CACHE_TIME_SHORT'])
def _get_flair(name):
    return get(moderator=True).get_flair(app.config['REDDIT_SUBREDDIT'], name)


def _uncache_flair(name):
    name = name.lower()
    cache.delete_memoized(_get_flair, name)


def get_flair(name, no_cache=False):
    name = name.lower()
    if no_cache:
        _uncache_flair(name)
    return _get_flair(name)


def update_flair_cache(name, flair):
    if flair.get('user', '').lower() != name.lower():
        # something went wrong
        logger.warning("update_flair_cache: name in dict %r isn't equivalent to name given %r, dropping key",
                       flair.get('user'), name)
        _uncache_flair(name)
        if flair.get('user'):
            _uncache_flair(flair['user'])
        return
    key = _get_flair.make_cache_key(_get_flair.uncached, name)
    cache.set(key, flair, timeout=_get_flair.cache_timeout)


@cache.cached(timeout=app.config['CACHE_TIME_LONG'], key_prefix='reddit_moderator_cache')
def get_moderators():
    return {u.name for u in get().get_moderators(app.config['REDDIT_SUBREDDIT'])}


@cache.cached(timeout=app.config['CACHE_TIME_LONG'], key_prefix='reddit_me_cache')
def get_me():
    return get(moderator=True).get_me().name


@cache.cached(timeout=app.config['CACHE_TIME_LONG'], key_prefix='reddit_mymod_cache')
def get_my_moderation():
    return [s.url for s in get(moderator=True).get_my_moderation()]
