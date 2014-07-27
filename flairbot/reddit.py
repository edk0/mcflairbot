from flask import session

import cssutils
import cssutils.css
import praw
import requests
import time

from .app import app, cache


moderator_scopes = {'identity', 'mysubreddits', 'modflair', 'flair'}

_access_expiry = -1
_access_info = None


def get(user_from_session=False, moderator=False):
    global _access_info, _access_expiry

    r = praw.Reddit('/u/mindcrack_flair_bot, by /u/edk141')
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
            info = r.refresh_access_information(app.config['REDDIT_REFRESH_TOKEN'])
            _access_info = (info['access_token'], info['refresh_token'])
            _access_expiry = time.time() + 3300  # give ourselves a 5-minute margin
    return r


@cache.cached(timeout=app.config['CACHE_TIME_LONG'], key_prefix='reddit_stylesheet_cache')
def get_stylesheet():
    tries = 3
    while tries > 0:
        time.sleep(3)
        r = requests.get('https://ssl.reddit.com/r/{}/stylesheet.css'.format(
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


def get_flair(name, no_cache=False):
    if no_cache:
        cache.delete_memoized(_get_flair, name)
    return _get_flair(name)


def update_flair_cache(name, flair):
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
