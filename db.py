import os
import pyodbc
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DB_SERVER = os.getenv("DB_SERVER", "ist210.database.windows.net")
DB_DATABASE = os.getenv("DB_DATABASE", "ist-210-work")
DB_USER = os.getenv("DB_USER", "CloudSA3b984a23")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_DRIVER = os.getenv("DB_DRIVER", "{ODBC Driver 18 for SQL Server}")
DB_TRUST_SERVER_CERTIFICATE = os.getenv("DB_TRUST_SERVER_CERTIFICATE", "yes")

def get_connection_string():
    """Build the ODBC connection string for Azure SQL Database."""
    driver = DB_DRIVER if DB_DRIVER.startswith("{") else f"{{{DB_DRIVER}}}"
    server_address = DB_SERVER if DB_SERVER.startswith("tcp:") else f"tcp:{DB_SERVER},1433"
    
    return (
        f"Driver={driver};"
        f"Server={server_address};"
        f"Database={DB_DATABASE};"
        f"Uid={DB_USER};"
        f"Pwd={DB_PASSWORD};"
        f"Encrypt=yes;"
        f"TrustServerCertificate={DB_TRUST_SERVER_CERTIFICATE};"
        f"Connection Timeout=15;"
    )

def get_db_connection():
    """Establish and return a new database connection."""
    conn_str = get_connection_string()
    return pyodbc.connect(conn_str)

def test_connection():
    """
    Test database connectivity.
    Returns: (success: bool, message: str, details: dict)
    """
    if not DB_PASSWORD or DB_PASSWORD == "YourAzureSqlPasswordHere":
        return False, "Database password not configured in .env", {"server": DB_SERVER, "database": DB_DATABASE, "user": DB_USER}
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DB_NAME() AS CurrentDb, @@VERSION AS Version, CURRENT_USER AS CurrentUser")
        row = cursor.fetchone()
        info = {
            "database": row[0],
            "version": row[1].split("\n")[0],
            "user": row[2],
            "server": DB_SERVER
        }
        cursor.close()
        conn.close()
        return True, "Successfully connected to Azure SQL Database", info
    except Exception as e:
        return False, str(e), {"server": DB_SERVER, "database": DB_DATABASE, "user": DB_USER}

def dict_from_row(cursor, row):
    """Convert a pyodbc Row into a dictionary using cursor description."""
    if row is None:
        return None
    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))

def execute_query(sql, params=(), fetch=None):
    """
    Safely execute a parameterized SQL query.
    Enforces Security by Design by strictly binding all parameters.
    
    fetch options:
      - 'all': returns list of dicts
      - 'one': returns single dict or None
      - 'commit': commits transaction and returns rowcount
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        
        if fetch == 'all':
            columns = [column[0] for column in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
            return results
        elif fetch == 'one':
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [column[0] for column in cursor.description]
            return dict(zip(columns, row))
        elif fetch == 'commit':
            conn.commit()
            return cursor.rowcount
        elif fetch == 'identity':
            # For inserts where we need SCOPE_IDENTITY()
            cursor.execute("SELECT SCOPE_IDENTITY()")
            identity = cursor.fetchone()[0]
            conn.commit()
            return identity
        else:
            conn.commit()
            return None
    finally:
        conn.close()
