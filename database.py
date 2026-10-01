"""
UPF Optimal Placer (UOP) - v2.0

File: database.py

Description:
Provides a context manager for SQLite database connections and utility functions for executing queries and inspecting the schema.

@authors: R. Rodriguez <raul.rodriguez@hcltech.com>, Y. Aldoori <yaseen.aldoori@windriver.com>, L. Popokh <leo.popokh@asato.ai>
@license: MIT
@copyright: Copyright (c) 2026 R. Rodriguez, Y. Aldoori, L. Popokh
"""

# Standard library imports
import sqlite3
from contextlib import contextmanager
from pathlib import Path

# Third-party libraries
import loguru


# Database configuration
# Path provided: database/network.db
DB_PATH = Path("database/network.db")

@contextmanager
def get_db_connection():
    """
    Context manager to handle SQLite connections.
    Ensures the connection is closed even if an error occurs.
    """
    try:
        if not DB_PATH.exists():
            loguru.logger.error(f"Database file not found at: {DB_PATH}")
            raise FileNotFoundError(f"Database file missing: {DB_PATH}")
            
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name
        loguru.logger.debug(f"Connected to database: {DB_PATH}")
        yield conn
    except sqlite3.Error as e:
        loguru.logger.error(f"Database connection error: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()
            loguru.logger.debug("Database connection closed")

def execute_query(query: str, params: tuple = ()):
    """
    Executes a query and returns all results.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        loguru.logger.debug(f"Executing query: {query} with params: {params}")
        cursor.execute(query, params)
        return cursor.fetchall()

def execute_single_query(query: str, params: tuple = ()):
    """
    Executes a query and returns only the first result.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        loguru.logger.debug(f"Executing single query: {query} with params: {params}")
        cursor.execute(query, params)
        return cursor.fetchone()
        
def get_all_tables():
   """
   Utility to list all tables in the database to debug schema issues.
   """
   query = "SELECT name FROM sqlite_master WHERE type='table';"
   with get_db_connection() as conn:
       cursor = conn.cursor()
       cursor.execute(query)
       tables = [row["name"] for row in cursor.fetchall()]
       loguru.logger.info(f"Tables found in database: {tables}")
       return tables

def get_table_columns(table_name: str):
    """
    Utility to list all columns of a specific table.
    """
    query = f"PRAGMA table_info({table_name});"
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [row["name"] for row in cursor.fetchall()]
        loguru.logger.info(f"Columns in {table_name}: {columns}")
        return columns 