# mindcrack flair bot

## Setup

In a virtualenv, or with sufficient privileges:

```console
$ pip install -r requirements.txt
```

Edit `instance/config.cfg`, copy keys from `instance/default.cfg` and change them to be sensible

pro tip: It'll probably need a real database eventually so just get it over with and install one now

## Run

`python manage.py runserver -d -r`

## uWSGI quickstart

If you want to run under uWSGI, `uwsgi.ini` exists and has enough settings to run the app.

To run on localhost:5000, just do:
```console
$ TESTING= uwsgi uwsgi.ini
```

For a more serious setup, create `instance/local.ini` and set up uwsgi sockets properly:
```ini
[uwsgi]
uwsgi-socket = flairbot.sock
```

Then, similar to before:
```console
$ uwsgi uwsgi.ini
```
