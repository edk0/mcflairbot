from flask import url_for
from datetime import datetime
from markupsafe import Markup
from sqlalchemy.types import TypeDecorator, String

import binascii
import os

from . import utils
from .app import db


class AsciiString(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if hasattr(value, 'encode'):
            value = value.encode('ascii')
        return value

    def process_result_value(self, value, dialect):
        if hasattr(value, 'decode'):
            value = value.decode('ascii')
        return value


class Trade(db.Model):
    id = db.Column(AsciiString(32), primary_key=True)
    status = db.Column(db.Enum('valid', 'invalid', 'finished'), default='valid')
    deleted = db.Column(db.Boolean(), default=False)

    creator = db.Column(db.String(32))
    creator_flair = db.Column(db.String(256))
    creator_flair_css = db.Column(db.String(64))

    target = db.Column(db.String(32))
    target_flair = db.Column(db.String(256))
    target_flair_css = db.Column(db.String(64))

    created = db.Column(db.DateTime())
    finalized = db.Column(db.DateTime())

    def __init__(self,
                 creator=None, creator_flair=None, creator_flair_css=None,
                 target=None, target_flair=None, target_flair_css=None):
        self.id = binascii.hexlify(os.urandom(16))
        self.creator = creator
        self.creator_flair = creator_flair
        self.creator_flair_css = creator_flair_css
        self.target = target
        self.target_flair = target_flair
        self.target_flair_css = target_flair_css
        self.created = datetime.utcnow()

    def accept_url(self, external=False):
        return url_for('trade_view', trade_id=self.id, _external=external)

    def set_status(self, status):
        self.status = status
        if status != 'valid':
            self.finalized = datetime.utcnow()

    @property
    def render_creator(self):
        return utils.render_flair(self.creator_flair, self.creator_flair_css)

    @property
    def render_target(self):
        return utils.render_flair(self.target_flair, self.target_flair_css)

    @classmethod
    def query_valid(cls):
        return cls.query.filter(cls.status == 'valid', cls.deleted != True)

    @classmethod
    def by_id(cls, id_, allow_invalid=False, allow_finished=False, allow_deleted=False):
        query = cls.query
        if not allow_invalid:
            query = query.filter(cls.status != 'invalid')
        if not allow_finished:
            query = query.filter(cls.status != 'finished')
        if not allow_deleted:
            query = query.filter(cls.deleted == False)
        result = query.filter(cls.id == id_).limit(1).all()
        if len(result) == 1:
            return result[0]
        else:
            return None

    def make_accept_token(self):
        self.accept_token = binascii.hexlify(os.urandom(16))

