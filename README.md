# mindcrack flair bot

## Setup

In a virtualenv, or with sufficient privileges:

```
pip install -r requirements.txt
```

Edit `instance/config.cfg`, copy keys from `instance/default.cfg` and change them to be sensible

pro tip: It'll probably need a real database eventually so just get it over with and install one now

## Run

`python manage.py runserver --debug --reload`
