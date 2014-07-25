from flask.ext.script import Manager

from flairbot.app import app

manager = Manager(app)

if __name__ == "__main__":
    manager.run()
