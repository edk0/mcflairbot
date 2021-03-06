from flask.ext.admin import Admin, BaseView, expose
from flask.ext.admin.contrib.sqla import ModelView

from sqlalchemy.sql import and_, or_, not_

from . import reddit, utils
from .app import app, cache, db
from .models import GiveawayLog, Trade


class AuthenticatedView(BaseView):
    def is_accessible(self):
        return utils.is_admin()


class AuthenticatedModelView(ModelView):
    def is_accessible(self):
        return utils.is_admin()


######


class IndexView(AuthenticatedView):
    @expose('/')
    def index(self):
        me = reddit.get_me()
        myflair = reddit.get_flair(me)
        myflair = utils.render_flair(myflair['flair_text'], myflair['flair_css_class'])
        mymod = ', '.join(sorted(reddit.get_my_moderation()))
        return self.render('admin/index.html', me=me, myflair=myflair, mymod=mymod)


class ListView(AuthenticatedView):
    def __init__(self, order, filter_, **kw):
        self.order = order
        self.filter = filter_
        super(ListView, self).__init__(**kw)

    @expose('/')
    @expose('/p/<int:page>')
    def index(self, page=1):
        trades = Trade.query.filter(self.filter).order_by(self.order).paginate(page, 50)
        return self.render('admin/log.html', trades=trades)


class CacheView(AuthenticatedView):
    @expose('/')
    def index(self):
        keymap = {}
        keys = cache.cache._client.keys(cache.cache.key_prefix + '*')
        l = len(cache.cache.key_prefix)
        for key in keys:
            key = key.decode('utf8')[l:]
            keymap[key] = cache.get(key)
        def _repr(v):
            if isinstance(v, dict) and 'flair_text' in v:
                return utils.render_flair(v['flair_text'], v.get('flair_css_class', None))
            else:
                return repr(v)
        return self.render('admin/cache.html', mapping=sorted(keymap.items()), repr=_repr)


class GiveawayLogView(AuthenticatedModelView):
    column_auto_select_related = True
    column_list = ('trade', 'trade.creator', 'trade.creator_flair', 'trade.creator_flair_css', 'target', 'target_flair', 'target_flair_css', 'target_ip')
    column_sortable_list = ('trade.creator', 'trade.creator_flair', 'trade.creator_flair_css', ('target', GiveawayLog.target), ('target_flair', GiveawayLog.target_flair), ('target_flair_css', GiveawayLog.target_flair_css), ('target_ip', GiveawayLog.target_ip))
    column_searchable_list = (Trade.creator, Trade.creator_flair, Trade.creator_flair_css, GiveawayLog.target, GiveawayLog.target_flair, GiveawayLog.target_flair_css, GiveawayLog.target_ip)
    can_create = False
    can_edit = False


######

admin = Admin(app, index_view=IndexView('Home', None, 'admin', '/admin', 'static'))
admin.add_view(ListView(Trade.finalized.desc(), and_(Trade.status == 'finished', Trade.deleted == False), name='Log', category='Trades', endpoint='trades-log'))
admin.add_view(ListView(Trade.created.desc(), and_(or_(Trade.status == 'valid', Trade.status == 'giveaway'), Trade.deleted == False), name='Open', category='Trades', endpoint='trades-open'))
admin.add_view(ListView(Trade.created.desc(), or_(Trade.deleted == True, Trade.status == 'invalid'), name='Invalid/Deleted', category='Trades', endpoint='trades-deleted'))
admin.add_view(AuthenticatedModelView(Trade, db.session, name='Database Model', category='Trades', endpoint='trades-db'))
admin.add_view(GiveawayLogView(GiveawayLog, db.session, name='Giveaways', endpoint='giveaway-db'))
admin.add_view(CacheView('Cache', endpoint='cache'))
