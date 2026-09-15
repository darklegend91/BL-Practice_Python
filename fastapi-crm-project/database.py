import psycopg

DB_CONFIG = {
    "dbname": "customer-management",
    "user": "adityapathania",
    "password": "",
    "host": "localhost",
    "port": "5432",
}

def get_db_connection():
    """Returns a connection with dictionary row mapping."""
    return psycopg.connect(**DB_CONFIG) # type:ignore