from flask import url_for

import binascii
import os

from .app import db


class Trade(db.Model):
    id = db.Column(db.String(32), primary_key=True)

    creator = db.Column(db.String(32))
    creator_flair = db.Column(db.String(256))

    target = db.Column(db.String(32))
    target_flair = db.Column(db.String(256))

    def __init__(self, creator, creator_flair, target=None, target_flair=None):
        self.id = binascii.hexlify(os.urandom(16))
        self.creator = creator
        self.creator_flair = creator_flair
        self.target = target
        self.target_flair = target_flair

    @property
    def accept_url(self):
        return url_for('trade_accept', self.id)

    @classmethod
    def by_id(cls, id_):
        return cls.query.get(id_)

    def make_accept_token(self):
        self.accept_token = binascii.hexlify(os.urandom(16))

