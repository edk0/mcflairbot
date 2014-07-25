from flask import Flask
from flask.ext.sqlalchemy import SQLAlchemy

app = Flask(__name__, instance_relative_config=True)
app.config.from_pyfile('default.cfg')
app.config.from_pyfile('config.cfg', silent=True)

db = SQLAlchemy(app)

from . import views
