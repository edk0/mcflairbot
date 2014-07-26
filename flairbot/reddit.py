from flask import session

import cssutils
import cssutils.css
import praw
import requests
import time

from .app import app, cache


moderator_scopes = {'identity', 'mysubreddits', 'modflair'}

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


@cache.cached(timeout=1800, key_prefix='reddit_stylesheet_cache')
def get_stylesheet():
    r = requests.get('https://ssl.reddit.com/r/{}/stylesheet.css'.format(
            app.config['REDDIT_SUBREDDIT']))
    sheet = cssutils.parseString(r.text)
    new = cssutils.css.CSSStyleSheet()
    for rule in sheet.cssRules.rulesOfType(cssutils.css.CSSRule.STYLE_RULE):
        for selector in rule.selectorList:
            if selector.selectorText == 'content':
                selector.selectorText = '.flair'
            if selector.selectorText.startswith('.flair'):
                new.add(rule)
    return new.cssText

