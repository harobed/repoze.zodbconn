import urlparse
from repoze.zodbconn.resolvers import RESOLVERS

class SimpleCleanup:
    def __init__(self, conn, environ):
        # N.B.:  do *not* create a cycle by holding on to 'environ'!
        self.cleaner = conn.close

    def __del__(self):
        self.cleaner()

class LoggingCleanup:
    logger = None

    def __init__(self, conn, environ):
        # N.B.:  do *not* create a cycle by holding on to 'environ'!
        self.conn = conn
        self.request_method = environ['REQUEST_METHOD']
        self.path_info = environ['PATH_INFO']
        self.query_string = environ.get('QUERY_STRING')
        self.loads_before, self.stores_before = conn.getTransferCounts()

    #############  WAAAAAAAAAAA!!!!!!########################################
    # For some insane reason, the coverage module thinks this entire method
    # is uncovered, in spite of the fact that the passing unit tests prove
    # that both code paths get executed.
    #########################################################################
    def __del__(self): #pragma NO COVERAGE
        loads_after, stores_after = self.conn.getTransferCounts()
        self.conn.close()
        if self.logger is not None:
            if self.query_string:
                url = '%s?%s' % (self.path_info, self.query_string)
            else:
                url = self.path_info
            loads = loads_after - self.loads_before
            stores = stores_after - self.stores_before
            self.logger.write('"%s","%s",%d,%d\n'
                                % (self.request_method, url, loads, stores))

class PersistentApplicationFinder:
    db = None

    def __init__(self, uri, appmaker, cleanup=SimpleCleanup):
        self.uri = uri
        self.appmaker = appmaker
        self.cleanup = cleanup

    def __call__(self, environ):
        if self.db is None:
            self.db = db_from_uri(self.uri)
        conn = self.db.open()
        root = conn.root()
        app = self.appmaker(root)
        environ['repoze.zodbconn.closer'] = self.cleanup(conn, environ)
        return app


def db_from_uri(uri):
    """Create a database from a list of database URIs and return it.

    uri can be either a whitespace-delimited string or a list of URIs
    as strings.
    """
    if isinstance(uri, basestring):
        uris = uri.strip().split()
    else:
        uris = uri
    databases = {}
    res = None
    for uri in uris:
        dbfactory = dbfactory_from_uri(uri)
        db = dbfactory()
        for name in db.databases:
            if name in databases:
                raise ValueError("database_name %r already in databases" %
                    name)
        # link the databases together
        databases.update(db.databases)
        db.databases = databases
        if res is None:
            # the first database in the list of URIs is the root
            res = db
    return res

def dbfactory_from_uri(uri):
    (scheme, netloc, path, query, frag) = urlparse.urlsplit(uri)
    resolver =  RESOLVERS.get(scheme)
    if resolver is None:
        raise ValueError('Unresolveable URI %s' % uri)
    _, _, _, dbfactory = resolver(uri)
    return dbfactory

