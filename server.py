import sys
import os
import time

from pyramid.config import Configurator
from sqlalchemy import (
    create_engine,
    Column,
    Boolean,
    MetaData,
    Integer,
    String,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import scoped_session, sessionmaker
from zope.sqlalchemy import ZopeTransactionExtension


Base = declarative_base(metadata=MetaData())
engine = create_engine('postgresql+psycopg2://localhost/fsppgg_test')
Session = scoped_session(sessionmaker(extension=ZopeTransactionExtension()))
Session.configure(bind=engine)


# Optionally, set up psycopg2 & SQLAlchemy to be greenlet-friendly.
# Note: psycogreen does not really monkey patch psycopg2 in the
# manner that gevent monkey patches socket.
#
if "PSYCOGREEN" in os.environ:

    # Do our monkey patching
    #
    from gevent.monkey import patch_all
    patch_all()
    from psycogreen.gevent import patch_psycopg
    patch_psycopg()

    using_gevent = True
else:
    using_gevent = False


if using_gevent:

    # Assuming that gevent monkey patched the builtin
    # threading library, we're likely good to use
    # SQLAlchemy's QueuePool, which is the default
    # pool class.  However, we need to make it use
    # threadlocal connections
    #
    #
    engine.pool._use_threadlocal = True


# View functions

def sleep_postgres(request):
    """ This handler asks Postgres to sleep for 5s and will
        block for 5s unless psycopg2 is set up (above) to be
        gevent-friendly.
    """
    Session().execute('SELECT pg_sleep(5)')
    return Todo.all_as_dict()


def sleep_python(request):
    """ This handler sleeps for 5s and will block for 5s unless
        gunicorn is using the gevent worker class.
    """
    time.sleep(5)
    return Todo.all_as_dict()


# Create our Pyramid app

config = Configurator()
config.include('pyramid_tm')
config.add_route('sleep_postgres', '/sleep/postgres/')
config.add_route('sleep_python', '/sleep/python/')
config.add_view(
    sleep_postgres,
    route_name='sleep_postgres',
    renderer='json',
)
config.add_view(
    sleep_python,
    route_name='sleep_python',
    renderer='json',
)
app = config.make_wsgi_app()


class Todo(Base):
    """ Small example model just to show you that SQLAlchemy is
        doing everything it should be doing.
    """
    __tablename__ = 'todo'

    id = Column(Integer, primary_key=True)
    title = Column(String)
    done = Column(Boolean)
    priority = Column(Integer)

    def as_dict(self):
        """ Return an individual Todo as a dictionary.
        """
        return {
            'id': self.id,
            'title': self.title,
            'done': self.done,
            'priority': self.priority
        }

    @classmethod
    def all_as_dict(cls):
        return [todo.as_dict() for todo in Session().query(cls).all()]


# Create the tables and populate it with some dummy data
#
def create_data():
    """ A helper function to create our tables and some Todo objects.
    """
    Base.metadata.create_all(engine)
    todos = []
    for i in range(50):
        todo = Todo(
            title="Slave for the man {0}".format(i),
            done=(i % 2 == 0),
            priority=(i % 5)
        )
        todos.append(todo)
    session = Session()
    session.add_all(todos)
    session.commit()


if __name__ == '__main__':

    if '-c' in sys.argv:
        create_data()
    else:
        app.run()
