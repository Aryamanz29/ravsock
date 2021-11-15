from ravsock.utils import create_database, create_tables

if create_database():
    create_tables()
