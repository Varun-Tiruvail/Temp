import sqlite3
from sqlite3 import Error
import pandas as pd

def count_reportees(manager_username):
    """Count how many reportees a manager has from the hierarchy file"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        return len(df[df['Manager'] == manager_username])
    except Exception as e:
        print(f"Error counting reportees: {e}")
        return 0

def create_connection(db_file):
    """ Create a database connection to a SQLite database """
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Error as e:
        print(e)
    return conn

def get_all_pending_approvals():
    """ Get all pending approvals (for superuser) """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, manager FROM pending_users WHERE is_approved=0"
    )
    approvals = cursor.fetchall()
    conn.close()
    return approvals

def initialize_databases():
    """ Initialize both temporary and final databases """
    # Temporary database for pending approvals
    temp_conn = create_connection('temp_database.db')
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            manager TEXT NOT NULL,
            is_approved INTEGER DEFAULT 0
        )
    ''')
    temp_conn.commit()
    
    # Final database for approved users
    final_conn = create_connection('final_database.db')
    final_cursor = final_conn.cursor()
    final_cursor.execute('''
        CREATE TABLE IF NOT EXISTS approved_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            manager TEXT NOT NULL,
            is_superuser INTEGER DEFAULT 0
        )
    ''')
    
    # Add superuser if not exists
    final_cursor.execute("SELECT * FROM approved_users WHERE username='Admin'")
    if not final_cursor.fetchone():
        final_cursor.execute(
            "INSERT INTO approved_users (username, password, manager, is_superuser) VALUES (?, ?, ?, ?)",
            ('Admin', 'mnbvcxz!@#098', 'None', 1)
        )
    final_conn.commit()
    
    temp_conn.close()
    final_conn.close()

def check_hierarchy(username):
    """ Check if username exists in the hierarchy Excel file """
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        return username in df['Manager'].values or username in df['Reportee'].values
    except Exception as e:
        print(f"Error reading hierarchy file: {e}")
        return False

def get_manager(username):
    """ Get manager for a given username from hierarchy """
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        manager = df[df['Reportee'] == username]['Manager'].values
        return manager[0] if len(manager) > 0 else None
    except Exception as e:
        print(f"Error getting manager: {e}")
        return None

# def get_reportee(username):
#     """ Get manager for a given username from hierarchy """
#     try:
#         df = pd.read_excel('employee_hierarchy.xlsx')
#         reportee = df[df['Manager'] == username]['Reportee'].values
#         return reportee[0] if len(reportee) > 0 else None
#     except Exception as e:
#         print(f"Error getting manager: {e}")
#         return None

def get_reportees(manager_username):
    """Get all reportees for a given manager from hierarchy"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        reportees = df[df['Manager'] == manager_username]['Reportee'].tolist()
        return reportees  # Returns list of all reportees (empty list if none)
    except Exception as e:
        print(f"Error getting reportees: {e}")
        return []

def add_pending_user(username, password, manager):
    """ Add user to temporary database for approval """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pending_users (username, password, manager) VALUES (?, ?, ?)",
        (username, password, manager)
    )
    conn.commit()
    conn.close()

def get_pending_approvals(manager_username=None):
    """ Get pending approvals - for specific manager or all if None """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    
    if manager_username:
        cursor.execute(
            "SELECT id, username, manager FROM pending_users WHERE manager=? AND is_approved=0",
            (manager_username,)
        )
    else:
        cursor.execute(
            "SELECT id, username, manager FROM pending_users WHERE is_approved=0"
        )
    
    approvals = cursor.fetchall()
    conn.close()
    return approvals

def disapprove_user(user_id):
    """ Remove user from temporary database (disapproval) """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM pending_users WHERE id=?",
        (user_id,)
    )
    conn.commit()
    conn.close()

def approve_user(user_id):
    """ Approve a user and move to final database """
    temp_conn = create_connection('temp_database.db')
    final_conn = create_connection('final_database.db')
    
    # Get user from temp database
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute(
        "SELECT username, password, manager FROM pending_users WHERE id=?",
        (user_id,)
    )
    user = temp_cursor.fetchone()
    
    if user:
        # Add to final database
        final_cursor = final_conn.cursor()
        final_cursor.execute(
            "INSERT INTO approved_users (username, password, manager) VALUES (?, ?, ?)",
            user
        )
        final_conn.commit()
        
        # Remove from temp database
        temp_cursor.execute(
            "DELETE FROM pending_users WHERE id=?",
            (user_id,)
        )
        temp_conn.commit()
    
    temp_conn.close()
    final_conn.close()

def validate_login(username, password):
    """ Validate user credentials and return user info with reportee count """
    conn = create_connection('final_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, manager, is_superuser FROM approved_users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()
    conn.close()
    
    if user:
        username, manager, is_superuser = user
        reportee_count = count_reportees(username) if not is_superuser else 0
        return (username, manager, bool(is_superuser), reportee_count)
    return None