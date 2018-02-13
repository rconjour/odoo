# -*- coding: utf-8 -*-
from werkzeug.contrib.sessions import SessionStore
import cPickle
import logging
import memcache

import openerp.tools.config

ONE_WEEK_IN_SECONDS = 60 * 60 * 24 * 7

logger = logging.getLogger(__name__)


class MemcachedSessionStore(SessionStore):
    """ Provide Odoo/Werkzeug Session Store support for Memcached. This class
    can be used to connect to a memcached server and use it for storing,
    getting and cleaning Odoo sessions. """

    def __init__(self, *args, **kwargs):
        """ Connect to the memcache server and get or use our default salt """
        memcached_uri = openerp.tools.config.get(
            'memcached', False)
        self.generate_salt = openerp.tools.config.get(
            'memcached_salt', 'Qurwa041VkccqzpIZptnDkUURfv1TaiH2HpBtdsd')
        self.memcached = memcache.Client([memcached_uri], debug=0)
        self.key_template = 'session:%s'

        logger.debug('HTTP sessions stored in memcached stored on: %s',
                     memcached_uri)

        super(MemcachedSessionStore, self).__init__(*args, **kwargs)

    def new(self):
        return self.session_class(
            {}, self.generate_key(self.generate_salt), True)

    def get_session_key(self, sid):
        if isinstance(sid, unicode):
            sid = sid.encode('utf-8')
        return self.key_template % sid

    def save(self, session):
        """ Save session data based on the users session id """
        data = cPickle.dumps(dict(session))
        key = self.get_session_key(session.sid)
        try:
            return self.memcached.set(key, data, ONE_WEEK_IN_SECONDS)
        except Exception as ex:
            logger.error("Error on setting session data", exc_info=ex)

    def delete(self, session):
        """ Delete session data based on the users session id """
        try:
            key = self.get_session_key(session.sid)
            return self.memcached.delete(key)
        except Exception as ex:
            logger.error("Error on deleting session data", exc_info=ex)

    def get(self, sid):
        """ Get session data based on the users session id """
        if not self.is_valid_key(sid):
            return self.new()

        key = self.get_session_key(sid)
        try:
            saved = self.memcached.get(key)
            data = cPickle.loads(saved) if saved else {}
        except Exception as ex:
            logger.error("Error on getting session data", exc_info=ex)
            data = {}
        return self.session_class(data, sid, False)