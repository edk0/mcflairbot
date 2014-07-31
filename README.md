# mindcrack flair bot

## Setup

In a virtualenv, or with sufficient privileges:

```console
$ pip install -r requirements.txt
```

Edit `instance/config.cfg`, copy keys from `instance/default.cfg` and change them to be sensible

pro tip: It'll probably need a real database eventually so just get it over with and install one now

## Run

```console
$ python manage.py runserver -d -r
```

## Reddit Authentication setup

Once you have reddit app details configured, you can configure OAuth access to the mod
account.

First, make sure you're logged into the correct account on reddit.

Then, with the web server running, run `manage.py setup-auth`:

```console
$ python manage.py setup-auth
Click the following link:
https://ssl.reddit.com/api/v1/authorize/.../
```

The link will take you to reddit's OAuth authorization page. Click “Allow”, and you'll
get the following output:

```console
Captured OAuth information for /u/accountname
Add the following to instance/config.cfg:
REDDIT_REFRESH_TOKEN = 'XXXXXXXXXXXXXXXXXXXXXXXXXXX'
```

Do as it says, then restart the web server (if you're running with uWSGI on the testing
configuration, this will happen automatically). If you configured everything properly, it'll
now be fully functional and ready to start trading flairs.

## uWSGI quickstart

If you want to run under uWSGI, `uwsgi.ini` exists and has enough settings to run the app.

To run on localhost:5000, just do:
```console
$ TESTING= uwsgi uwsgi.ini
```

There are a few extra things that happen when `TESTING` is set:

* An HTTP server runs on localhost:5000 (both IPv4 and IPv6).
* `/static` is mapped to serve static files from `flairbot/static`.
* uWSGI will be reloaded any time the Python sources, or `instance/config.cfg`, are modified.

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
