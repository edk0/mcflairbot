from flask.ext.script import Manager
from flask.ext.migrate import Migrate, MigrateCommand

from flairbot.app import app, db
from flairbot import utils

manager = Manager(app)
migrate = Migrate(app, db)

manager.add_command('db', MigrateCommand)

manager.add_command('setup-auth', utils.AuthCommand)
manager.add_command('stats', utils.StatsCommand)

if __name__ == "__main__":
    manager.run()
