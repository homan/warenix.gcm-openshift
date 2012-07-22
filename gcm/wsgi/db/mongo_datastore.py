import os
from pymongo.connection import Connection

def get_db():
    app_name = os.environ['OPENSHIFT_APP_NAME']
    db_host = os.environ['OPENSHIFT_NOSQL_DB_HOST']
    db_port = int(os.environ['OPENSHIFT_NOSQL_DB_PORT'])
    db_username = os.environ['OPENSHIFT_NOSQL_DB_USERNAME']
    db_password = os.environ['OPENSHIFT_NOSQL_DB_PASSWORD']

    connection = Connection(db_host, db_port)
    db = connection[app_name]
    db.authenticate(db_username, db_password)
    return db
