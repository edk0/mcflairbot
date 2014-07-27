from flask.ext.admin import BaseView, expose
from flask.ext.admin.contrib.sqla import ModelView

from . import utils
from .app import app, admin, db
from .models import Trade


class AuthenticatedView(BaseView):
    def is_accessible(self):
        return utils.is_admin()


class AuthenticatedModelView(ModelView):
    def is_accessible(self):
        return utils.is_admin()


######


class ListView(AuthenticatedView):
    def __init__(self, order, filters, **kw):
        self.order = order
        self.filters = filters
        super(ListView, self).__init__(**kw)

    @expose('/')
    @expose('/p/<int:page>')
    def index(self, page=1):
        trades = Trade.query.filter(*self.filters).order_by(self.order).paginate(page, 50)
        return self.render('admin/log.html', trades=trades)


######

admin.add_view(ListView(Trade.finalized.desc(), (Trade.status == 'finished',), name='Log', category='Trades', endpoint='trades-log'))
admin.add_view(ListView(Trade.finalized.desc(), (Trade.status == 'valid',), name='Open', category='Trades', endpoint='trades-open'))
admin.add_view(ListView(Trade.finalized.desc(), (Trade.status != 'valid', Trade.status != 'finished'), name='Invalid/Deleted', category='Trades', endpoint='trades-deleted'))
admin.add_view(AuthenticatedModelView(Trade, db.session, name='Database Model', category='Trades', endpoint='trades-db'))
