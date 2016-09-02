""" The pygamelaunch db module.

Looks after everything database related.
"""
import bcrypt
import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey

Base = declarative_base()

class Database:
    """The database connection class."""
    def __init__(self, path="users.db"):
        self.__engine = sqlalchemy.create_engine('sqlite:///' + path)
        self.__session = sqlalchemy.orm.sessionmaker()
        self.__session.configure(bind=self.__engine)

    def create(self):
        """Create a database instance.

        Only use this to create a new database if you don't have an
        existing database file.
        """
        Base.metadata.create_all(self.__engine)

    def begin(self):
        """Start a new database session."""
        return self.__session()

class User(Base):
    """A user row in the users database."""
    # pylint: disable=too-few-public-methods, no-init

    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)
    salt = Column(String)
    email = Column(String)

    def __repr__(self):
        return "<User(id='{}', name='{}', pass='{}', salt='{}')>".format(
            self.id, self.username, self.password, self.salt)

class Playing(Base):
    """A row representing a currently playing user."""
    # pylint: disable=too-few-public-methods, no-init
    __tablename__ = 'playing'

    id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    since = Column(Integer)
    record = Column(String)

class CreateUser:
    """Create a new user."""
    def __init__(self, user):
        self.__user = user
        self.__salt = ''
        self.__hash = ''

    def add_pass(self, password):
        """Add a password to the user."""
        self.__hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt())

    def create(self):
        """Create the user database row."""
        return User(username=self.__user,
                    password=self.__hash,
                    salt=self.__salt)

def create_password(password):
    """Create a hashed password."""
    return ('', bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()))

def update_password(user, password):
    """Update a user's password hash."""
    salt, digest = create_password(password)
    user.password = digest
    user.salt = salt

def create_user(name, password, email):
    """Create a user."""
    salt, digest = create_password(password)
    return User(username=name, password=digest, salt=salt, email=email)

def add_user(database, user):
    """Add a user to the database."""
    session = database.begin()
    session.add(user)
    session.commit()
