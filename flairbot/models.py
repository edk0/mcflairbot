import binascii
import os

from .app import db


class Trade(db.Model):
    id = db.Column(db.String(32), primary_key=True)
    accept_token = db.Column(db.String(32))

    creator = db.Column(db.String(32))
    creator_flair = db.Column(db.String(256))

    target = db.Column(db.String(32))
    target_flair = db.Column(db.String(256))

    @classmethod
    def by_id(cls, id_):
        return cls.query.get(id_)

    def make_accept_token(self):
        self.accept_token = binascii.hexlify(os.urandom(16))

