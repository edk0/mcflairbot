import praw

from .app import app


def get():
    r = praw.Reddit('/u/mindcrack_flair_bot, by /u/edk141')
    r.set_oauth_app_info(app.config['REDDIT_CLIENT_ID'],
                         app.config['REDDIT_CLIENT_SECRET'],
                         app.config['REDDIT_REDIRECT_URI'])
    return r

