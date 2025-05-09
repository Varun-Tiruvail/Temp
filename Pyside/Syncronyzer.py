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

    # def merge_databases(self, db1_path, db2_path, db_name):
    #     self.update_log.emit(f"\nSyncing {db_name}...")
        
    #     # Connect to both databases
    #     conn1 = sqlite3.connect(db1_path)
    #     conn2 = sqlite3.connect(db2_path)
        
    #     try:
    #         # Add last_modified column if not exists
    #         for conn in [conn1, conn2]:
    #             conn.execute('PRAGMA foreign_keys = ON;')
    #             conn.execute('''
    #                 CREATE TABLE IF NOT EXISTS _sync_meta (
    #                     table_name TEXT PRIMARY KEY,
    #                     last_modified TEXT
    #                 );
    #             ''')
                
    #             # Get all tables excluding metadata table
    #             tables = conn.execute("""
    #                 SELECT name FROM sqlite_master 
    #                 WHERE type='table' AND name NOT LIKE '_sync_%'
    #             """).fetchall()
                
    #             for table in tables:
    #                 table = table[0]
    #                 try:
    #                     conn.execute(f'''
    #                         ALTER TABLE {table} 
    #                         ADD COLUMN _sync_last_modified TEXT
    #                         DEFAULT '1970-01-01T00:00:00'
    #                     ''')
    #                 except sqlite3.OperationalError:
    #                     pass  # Column already exists

    #         # Sync data between databases
    #         for source_conn, target_conn in [(conn1, conn2), (conn2, conn1)]:
    #             source_cur = source_conn.cursor()
    #             target_cur = target_conn.cursor()

    #             # Get all tables
    #             tables = source_cur.execute("""
    #                 SELECT name FROM sqlite_master 
    #                 WHERE type='table' AND name NOT LIKE '_sync_%'
    #             """).fetchall()

    #             for table in tables:
    #                 table = table[0]
    #                 self.update_log.emit(f"  Processing table: {table}")
                    
    #                 # Get max sync time from target
    #                 target_cur.execute('''
    #                     SELECT last_modified FROM _sync_meta 
    #                     WHERE table_name = ?
    #                 ''', (table,))
    #                 target_max_time = target_cur.fetchone()
    #                 target_max_time = target_max_time[0] if target_max_time else None

    #                 # Get new records from source
    #                 # query = f'''
    #                 #     SELECT * FROM {table} 
    #                 #     WHERE _sync_last_modified > ? OR ? IS NULL
    #                 # ''' if target_max_time else f"SELECT * FROM {table}"
    #                 # source_cur.execute(query, (target_max_time, target_max_time))
                    

    #                 # if target_max_time:
    #                 #     query = f'''
    #                 #         SELECT * FROM {table} 
    #                 #         WHERE _sync_last_modified > ? OR ? IS NULL
    #                 #     '''
    #                 #     params = (target_max_time, target_max_time)
    #                 # else:
    #                 #     query = f"SELECT * FROM {table}"
    #                 #     params = ()

    #                 if target_max_time:
    #                     query = f'''
    #                         SELECT * FROM {table} 
    #                         WHERE datetime(_sync_last_modified) > datetime(?)
    #                     '''
    #                     params = (target_max_time,)

    #                 else:
    #                     query = f"SELECT * FROM {table}"
    #                     params = ()

    #                 source_cur.execute(query, params)

    #                 new_records = source_cur.fetchall()


    #                 if not new_records:
    #                     continue

    #                 # Get column names
    #                 source_cur.execute(f"PRAGMA table_info({table})")
    #                 columns = [col[1] for col in source_cur.fetchall()]

    #                 # Validate record structure
    #                 valid_records = []
    #                 for record in new_records:
    #                     if len(record) != len(columns):
    #                         self.update_log.emit(f"    Skipping invalid record: {record}")
    #                         continue
    #                     valid_records.append(record)

    #                 # Insert records with column count validation
    #                 placeholders = ', '.join(['?'] * len(columns))
    #                 insert_sql = f'''
    #                     INSERT OR REPLACE INTO {table} 
    #                     VALUES ({placeholders})
    #                 '''

    #                 for record in valid_records:
    #                     try:
    #                         # Verify parameter count matches column count
    #                         if len(record) != len(columns):
    #                             raise ValueError("Column count mismatch")
                                
    #                         target_cur.execute(insert_sql, record)
    #                     except Exception as e:
    #                         self.update_log.emit(f"    Insert error: {str(e)}")
    #                         self.resolve_conflicts(target_cur, table, dict(zip(columns, record)))

    #                 # Update sync metadata
    #                 if valid_records:
    #                     try:
    #                         max_time = max(
    #                             r[columns.index('_sync_last_modified')] 
    #                             for r in valid_records
    #                         )
    #                         target_cur.execute('''
    #                             INSERT OR REPLACE INTO _sync_meta 
    #                             VALUES (?, ?)
    #                         ''', (table, max_time))
    #                     except ValueError:
    #                         self.update_log.emit("    No valid timestamps found")

    #                 target_conn.commit()

    #                 # # Insert or replace records
    #                 # placeholders = ', '.join(['?'] * len(columns))
    #                 # insert_sql = f'''
    #                 #     INSERT OR REPLACE INTO {table} 
    #                 #     VALUES ({placeholders})
    #                 # '''
    #                 ####################
    #                 for record in new_records:
    #                     # Convert to dict for safe access
    #                     record_dict = dict(zip(columns, record))
    #                     record_dict['_sync_last_modified'] = datetime.now().isoformat()
                        
    #                     try:
    #                         target_cur.execute(insert_sql, tuple(record_dict.values()))
    #                     except sqlite3.IntegrityError as e:
    #                         self.update_log.emit(f"    Conflict resolved: {str(e)}")
    #                         # Handle foreign key constraints
    #                         self.resolve_conflicts(target_cur, table, record_dict)
    #                         ####################

    #                 # Update sync metadata

    #                 # max_time = max(r[columns.index('_sync_last_modified')] for r in new_records)

    #                 # if new_records:
    #                 #     max_time = max(r[columns.index('_sync_last_modified')] for r in new_records)
    #                 # else:
    #                 #     max_time = target_max_time  # Or datetime.now().isoformat()

    #                 # target_cur.execute('''
    #                 #     INSERT OR REPLACE INTO _sync_meta 
    #                 #     VALUES (?, ?)
    #                 # ''', (table, max_time))
    #                 ##########################
    #                 if new_records:
    #                     valid_times = [
    #                         r[columns.index('_sync_last_modified')] 
    #                         for r in new_records 
    #                         if r[columns.index('_sync_last_modified')] is not None
    #                     ]
    #                     max_time = max(valid_times) if valid_times else target_max_time
                        
    #                     # Update current time if no valid times
    #                     if not max_time:
    #                         max_time = datetime.now().isoformat()

    #                     target_cur.execute('''
    #                         INSERT OR REPLACE INTO _sync_meta 
    #                         VALUES (?, ?)
    #                     ''', (table, max_time))
    #                 #####################

    #             target_conn.commit()

    #     finally:
    #         conn1.close()
    #         conn2.close()


    def merge_databases(self, db1_path, db2_path, db_name):
        self.update_log.emit(f"\n🔄 Syncing {db_name}...")
        
        try:
            # Connect to databases
            conn1 = sqlite3.connect(db1_path)
            conn2 = sqlite3.connect(db2_path)
            
            # Configure connection settings
            for conn in [conn1, conn2]:
                conn.execute('PRAGMA journal_mode=WAL')
                conn.execute('PRAGMA foreign_keys=ON')

            # Initialize schema for both databases
            with conn1, conn2:
                # Create sync metadata table
                conn1.execute('''CREATE TABLE IF NOT EXISTS _sync_meta (
                    table_name TEXT PRIMARY KEY,
                    last_modified TEXT NOT NULL DEFAULT '1970-01-01T00:00:00'
                )''')
                
                conn2.execute('''CREATE TABLE IF NOT EXISTS _sync_meta (
                    table_name TEXT PRIMARY KEY,
                    last_modified TEXT NOT NULL DEFAULT '1970-01-01T00:00:00'
                )''')

                # Add sync column to all tables
                for conn in [conn1, conn2]:
                    tables = conn.execute('''
                        SELECT name FROM sqlite_master
                        WHERE type='table'
                        AND name NOT LIKE 'sqlite_%'
                        AND name NOT LIKE '_sync_%'
                    ''').fetchall()

                    for (table_name,) in tables:
                        try:
                            conn.execute(f'''
                                ALTER TABLE "{table_name}"
                                ADD COLUMN _sync_last_modified TEXT 
                                NOT NULL DEFAULT '1970-01-01T00:00:00'
                            ''')
                        except sqlite3.OperationalError as e:
                            if "duplicate column name" not in str(e):
                                raise

            # Bidirectional sync
            for source, target in [(conn1, conn2), (conn2, conn1)]:
                with source:
                    source_cur = source.cursor()
                    target_cur = target.cursor()

                    # Get list of user tables
                    tables = source_cur.execute('''
                        SELECT name FROM sqlite_master
                        WHERE type='table'
                        AND name NOT LIKE 'sqlite_%'
                        AND name NOT LIKE '_sync_%'
                    ''').fetchall()

                    for (table_name,) in tables:
                        self.update_log.emit(f"  📊 Processing table: {table_name}")
                        
                        # 1. Get last sync time from target
                        target_cur.execute('''
                            SELECT last_modified FROM _sync_meta
                            WHERE table_name = ?
                        ''', (table_name,))
                        target_time_row = target_cur.fetchone()
                        last_sync_time = target_time_row[0] if target_time_row else '1970-01-01T00:00:00'

                        # 2. Get new/modified records from source
                        source_cur.execute(f'''
                            SELECT * FROM "{table_name}"
                            WHERE datetime(_sync_last_modified) > datetime(?)
                        ''', (last_sync_time,))
                        new_records = source_cur.fetchall()

                        if not new_records:
                            continue

                        # 3. Get column information
                        source_cur.execute(f'PRAGMA table_info("{table_name}")')
                        columns = [col[1] for col in source_cur.fetchall()]
                        column_count = len(columns)

                        # 4. Prepare insert statement
                        placeholders = ', '.join(['?'] * column_count)
                        insert_sql = f'''
                            INSERT OR REPLACE INTO "{table_name}"
                            VALUES ({placeholders})
                        '''

                        # 5. Process records
                        current_time = datetime.now().isoformat()
                        valid_records = []
                        
                        for record in new_records:
                            if len(record) != column_count:
                                self.update_log.emit(f"    ⚠️ Skipping malformed record in {table_name}")
                                continue
                                
                            # Update sync timestamp
                            record_list = list(record)
                            sync_index = columns.index('_sync_last_modified')
                            record_list[sync_index] = current_time
                            valid_records.append(tuple(record_list))

                        # 6. Insert records
                        if valid_records:
                            try:
                                target_cur.executemany(insert_sql, valid_records)
                                target.commit()
                                
                                # Update sync metadata
                                target_cur.execute('''
                                    INSERT OR REPLACE INTO _sync_meta
                                    VALUES (?, ?)
                                ''', (table_name, current_time))
                                target.commit()
                                
                            except sqlite3.Error as e:
                                self.update_log.emit(f"    ❌ Error syncing {table_name}: {str(e)}")
                                target.rollback()

            self.update_log.emit("✅ Sync completed successfully!")
            
        except Exception as e:
            self.update_log.emit(f"🔥 Critical error: {str(e)}")
            raise
        finally:
            # Cleanup WAL files
            for conn in [conn1, conn2]:
                if conn:
                    conn.execute('PRAGMA wal_checkpoint(FULL)')
                    conn.close()


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