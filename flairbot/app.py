from flask import Flask
from flask.ext.admin import Admin
from flask.ext.cache import Cache
from flask.ext.sqlalchemy import SQLAlchemy
from flask_debugtoolbar import DebugToolbarExtension

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('default.cfg')
app.config.from_pyfile('config.cfg', silent=True)

cache = Cache(app)

db = SQLAlchemy(app)

toolbar = DebugToolbarExtension(app)

if not app.debug:
    import logging
    handler = logging.FileHandler('app.log')
    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)

from . import admin, views, utils
