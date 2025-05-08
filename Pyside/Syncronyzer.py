import sys
import sqlite3
import os
import shutil
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QLabel, QLineEdit, QPushButton, QTextEdit, QFileDialog
)
from PySide6.QtCore import QThread, Signal

class DBSyncThread(QThread):
    update_log = Signal(str)
    finished = Signal()

    def __init__(self, primary_path, secondary_path):
        super().__init__()
        self.primary_path = primary_path
        self.secondary_path = secondary_path
        self.databases = ['hierarchy.db', 'feedback.db', 'attendance.db']

    def run(self):
        try:
            for db_name in self.databases:
                self.sync_database(db_name)
            self.update_log.emit("\nSync completed successfully!")
        except Exception as e:
            self.update_log.emit(f"\nError: {str(e)}")
        finally:
            self.finished.emit()

    def sync_database(self, db_name):
        primary_db = f"{self.primary_path}/{db_name}"
        secondary_db = f"{self.secondary_path}/{db_name}"

        # Create database if not exists
        for path in [primary_db, secondary_db]:
            if not os.path.exists(path):
                open(path, 'a').close()

        # Merge both databases
        self.merge_databases(primary_db, secondary_db, db_name)

    def merge_databases(self, db1_path, db2_path, db_name):
        self.update_log.emit(f"\nSyncing {db_name}...")
        
        # Connect to both databases
        conn1 = sqlite3.connect(db1_path)
        conn2 = sqlite3.connect(db2_path)
        
        try:
            # Add last_modified column if not exists
            for conn in [conn1, conn2]:
                conn.execute('''
                    PRAGMA foreign_keys = ON;
                    CREATE TABLE IF NOT EXISTS _sync_meta (
                        table_name TEXT PRIMARY KEY,
                        last_modified TEXT
                    );
                ''')
                
                # Get all tables excluding metadata table
                tables = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE '_sync_%'
                """).fetchall()
                
                for table in tables:
                    table = table[0]
                    try:
                        conn.execute(f'''
                            ALTER TABLE {table} 
                            ADD COLUMN _sync_last_modified TEXT
                        ''')
                    except sqlite3.OperationalError:
                        pass  # Column already exists

            # Sync data between databases
            for source_conn, target_conn in [(conn1, conn2), (conn2, conn1)]:
                source_cur = source_conn.cursor()
                target_cur = target_conn.cursor()

                # Get all tables
                tables = source_cur.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE '_sync_%'
                """).fetchall()

                for table in tables:
                    table = table[0]
                    self.update_log.emit(f"  Processing table: {table}")
                    
                    # Get max sync time from target
                    target_cur.execute('''
                        SELECT last_modified FROM _sync_meta 
                        WHERE table_name = ?
                    ''', (table,))
                    target_max_time = target_cur.fetchone()
                    target_max_time = target_max_time[0] if target_max_time else None

                    # Get new records from source
                    query = f'''
                        SELECT * FROM {table} 
                        WHERE _sync_last_modified > ? OR ? IS NULL
                    ''' if target_max_time else f"SELECT * FROM {table}"
                    source_cur.execute(query, (target_max_time, target_max_time))
                    new_records = source_cur.fetchall()

                    if not new_records:
                        continue

                    # Get column names
                    source_cur.execute(f"PRAGMA table_info({table})")
                    columns = [col[1] for col in source_cur.fetchall()]

                    # Insert or replace records
                    placeholders = ', '.join(['?'] * len(columns))
                    insert_sql = f'''
                        INSERT OR REPLACE INTO {table} 
                        VALUES ({placeholders})
                    '''
                    
                    for record in new_records:
                        # Convert to dict for safe access
                        record_dict = dict(zip(columns, record))
                        record_dict['_sync_last_modified'] = datetime.now().isoformat()
                        
                        try:
                            target_cur.execute(insert_sql, tuple(record_dict.values()))
                        except sqlite3.IntegrityError as e:
                            self.update_log.emit(f"    Conflict resolved: {str(e)}")
                            # Handle foreign key constraints
                            self.resolve_conflicts(target_cur, table, record_dict)

                    # Update sync metadata
                    max_time = max(r[columns.index('_sync_last_modified')] for r in new_records)
                    target_cur.execute('''
                        INSERT OR REPLACE INTO _sync_meta 
                        VALUES (?, ?)
                    ''', (table, max_time))

                target_conn.commit()

        finally:
            conn1.close()
            conn2.close()

    def resolve_conflicts(self, cursor, table, record):
        # Custom conflict resolution logic
        if table == 'employees':
            # Handle employee hierarchy conflicts
            cursor.execute('''
                SELECT id FROM employees 
                WHERE name = ? AND position = ?
            ''', (record['name'], record['position']))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing record
                record['id'] = existing[0]
                cursor.execute('''
                    UPDATE employees SET 
                    manager_id = ?, 
                    _sync_last_modified = ?
                    WHERE id = ?
                ''', (record['manager_id'], record['_sync_last_modified'], record['id']))
            else:
                # Insert as new record
                columns = [c for c in record.keys() if c != 'id']
                values = [record[c] for c in columns]
                placeholders = ', '.join(['?'] * len(columns))
                cursor.execute(f'''
                    INSERT INTO employees ({','.join(columns)}) 
                    VALUES ({placeholders})
                ''', values)

class SyncApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Database Sync Tool")
        self.setGeometry(100, 100, 600, 400)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Path Selection
        self.path1_input = QLineEdit()
        self.path2_input = QLineEdit()
        browse1_btn = QPushButton("Browse Path 1")
        browse2_btn = QPushButton("Browse Path 2")
        
        browse1_btn.clicked.connect(lambda: self.select_path(self.path1_input))
        browse2_btn.clicked.connect(lambda: self.select_path(self.path2_input))
        
        layout.addWidget(QLabel("Network Path 1:"))
        layout.addWidget(self.path1_input)
        layout.addWidget(browse1_btn)
        layout.addWidget(QLabel("Network Path 2:"))
        layout.addWidget(self.path2_input)
        layout.addWidget(browse2_btn)
        
        # Sync Button
        sync_btn = QPushButton("Start Synchronization")
        sync_btn.clicked.connect(self.start_sync)
        layout.addWidget(sync_btn)
        
        # Log Output
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        layout.addWidget(self.log_output)
        
        self.sync_thread = None

    def select_path(self, input_field):
        path = QFileDialog.getExistingDirectory(self, "Select Network Path")
        if path:
            input_field.setText(path)

    def start_sync(self):
        path1 = self.path1_input.text()
        path2 = self.path2_input.text()
        
        if not path1 or not path2:
            self.log_output.append("Please select both network paths!")
            return
            
        if self.sync_thread and self.sync_thread.isRunning():
            self.log_output.append("Sync already in progress!")
            return
            
        self.sync_thread = DBSyncThread(path1, path2)
        self.sync_thread.update_log.connect(self.log_output.append)
        self.sync_thread.finished.connect(self.on_sync_finished)
        self.sync_thread.start()
        self.log_output.append("Starting synchronization...")

    def on_sync_finished(self):
        self.log_output.append("Sync process completed!")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SyncApp()
    window.show()
    sys.exit(app.exec())