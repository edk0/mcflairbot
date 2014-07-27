from flask import Flask
from flask.ext.admin import Admin
from flask.ext.cache import Cache
from flask.ext.sqlalchemy import SQLAlchemy

try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('default.cfg')
app.config.from_pyfile('config.cfg', silent=True)

admin = Admin(app)

cache = Cache(app)

db = SQLAlchemy(app)

from . import admin, views
