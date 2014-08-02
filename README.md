# mindcrack flair bot

## Setup

In a virtualenv, or with sufficient privileges:

```console
$ pip install -r requirements.txt
```

### Initial configuration

The app takes its configuration from `instance/config.cfg`, then `instance/default.cfg` (but the
former doesn't need to exist).

You should create `instance/config.cfg` and set a few keys now:
* `REDDIT_SUBREDDIT` to the name of a test subreddit you moderate
* `STYLE_SUBREDDIT` to `'mindcrack'`—necessary to generate the flair stylesheet
* `SECRET_KEY` to something random.
  A good way to get something random is to run `python -c 'import os;print os.urandom(24)'` and
  copy the output verbatim.

### Database

If you're only going to be doing a bit of hacking/local testing, don't bother with a database. The
default configuration uses SQLite - just run `python manage.py db upgrade` to get started.

Set up a database of your choice - MySQL/MariaDB is easy. Make sure MySQL's `wait_timeout` is at
least 2 hours (7200), although 28800 is probably more sensible.

If you do use MySQL, add this line to `instance/config.cfg`:

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://USERNAME:PASSWORD@HOST/DATABASE'
```

(obviously, you should change my placeholder names, unless your configuration is rather strange).
The syntax is similar for other kinds of database - consult the SQLAlchemy docs if you're
interested.

Databases are more useful when they have tables in them, so run:

```console
$ python manage.py db upgrade
```

…to get some. You'll also need to do this every time the database schema changes; since it doesn't
hurt to do it when it _hasn't_ changed, I recommend you just run it every time you `git pull`.

### Reddit

#### App Setup

In order to authenticate with Reddit's OAuth API, you'll need to visit
https://ssl.reddit.com/prefs/apps/ and create an app using the form there. You can call it whatever
you like. Make sure it's set as a web app, and set the redirect URL to `http://localhost:5000/`.

Once the app is created, you'll get a client ID and a secret from Reddit. Put them, and the
redirect URL, into `instance/config.cfg`, with the keys `REDDIT_CLIENT_ID`,
`REDDIT_CLIENT_SECRET`, and `REDDIT_REDIRECT_URI` respectively.

#### OAuth

Once you have reddit app details configured, you can configure OAuth access to the mod account.

First, make sure you're logged into the correct account on reddit.

Now run the server! It won't work very well yet because we haven't got the OAuth details yet, but
it'll be able to catch Reddit's response to our authorization request. You can run it with:

```console
$ python manage.py runserver
```

Then, with the web server running, run `manage.py setup-auth`:

```console
$ python manage.py setup-auth
Click the following link:
https://ssl.reddit.com/api/v1/authorize/.../
```

The link will take you to reddit's OAuth authorization page. Click “Allow”, and you'll get the
following output:

```console
Captured OAuth information for /u/accountname
Add the following to instance/config.cfg:
REDDIT_REFRESH_TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXX'
```

Do as it says, then restart the web server. If you configured everything properly, it'll now be
fully functional and ready to start trading flairs.

## Run

I recommend that you normally run the server with uWSGI (there are some notes about doing that
below). However, it's generally better when debugging to use Flask's built-in test server:

```console
$ python manage.py runserver -d -r
```

You can enable more debugging stuff by adding:

```python
DEBUG = True
```

…to `instance/config.cfg`

### uWSGI

If you want to run under uWSGI, `uwsgi.ini` exists and has enough settings to run the app.

To run on localhost:5000, just do:
```console
$ TESTING= uwsgi uwsgi.ini
```

There are a few extra things that happen when `TESTING` is set:

* An HTTP server runs on localhost:5000 (both IPv4 and IPv6).
* `/static` is mapped to serve static files from `flairbot/static`.
* uWSGI will be reloaded any time the Python sources, or `instance/config.cfg`, are modified.
* There will only be one uWSGI process (instead of cores × 2), so Flask debugging should work.

These aren't appropriate for a production environment. For a more serious setup, create
`instance/local.ini` and set up uwsgi sockets properly:
```ini
[uwsgi]
uwsgi-socket = flairbot.sock
```

Then, similar to before:
```console
$ uwsgi uwsgi.ini
```
