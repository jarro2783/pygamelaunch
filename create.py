#!/usr/bin/python

import db

def create_db():
    d = db.Database()
    d.create()

if __name__ == "__main__":
    create_db()
