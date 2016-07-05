import sqlalchemy
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey
import hashlib
import os

Base = declarative_base()

class Database:
    def __init__(self):
        self.__engine = sqlalchemy.create_engine('sqlite:///users.db')
        self.__Session = sqlalchemy.orm.sessionmaker()
        self.__Session.configure(bind=self.__engine)

    def create(self):
        Base.metadata.create_all(self.__engine)

    def begin(self):
        return self.__Session()

class User(Base):
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
    __tablename__ = 'playing'

    id = Column(Integer, ForeignKey('users.id'), primary_key=True)
    since = Column(Integer)
    record = Column(String)

class CreateUser:
    def __init__(self, user):
        self.__user = user
        self.__salt = os.urandom(128)
        self.__hash = hashlib.sha256(self.__salt)

    def add_pass(self, c):
        self.__hash.update(c.encode('utf-8'))

    def create(self):
        return User(username=self.__user, password=self.__hash.digest(),
            salt=self.__salt)

def create_password(password):
    salt = os.urandom(16)
    s = hashlib.sha256(salt)
    s.update(password.encode('utf-8'))
    return (salt, s.digest())

def update_password(user, password):
    salt, digest = create_password(password)
    user.password = digest
    user.salt = salt

def create_user(name, password, email):
    salt, digest = create_password(password)
    return User(username=name, password=digest, salt=salt, email=email)

def add_user(db, user):
    s = db.begin()
    s.add(user)
    s.commit()
