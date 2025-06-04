import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                              QPushButton, QComboBox, QListWidget, QDateEdit, QTableView, QCheckBox, QGroupBox,
                              QMessageBox, QFileDialog, QAbstractItemView, QProgressBar, QSystemTrayIcon, QMenu)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings, QDate
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
import pyadomd

class CubeConnection:
    def __init__(self, server, database):
        self.connection_string = f"Provider=MSOLAP;Data Source={server};Initial Catalog={database};Integrated Security=SSPI;"
        self.conn = None

    def connect(self):
        try:
            self.conn = pyadomd.Pyadomd(self.connection_string)
            self.conn.open()
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def get_metadata(self):
        if not self.conn:
            return []
        try:
            return [row.CUBE_NAME for row in self.conn.get_cubes()]
        except Exception as e:
            print(f"Metadata error: {e}")
            return []

    def get_columns(self, cube_name):
        if not self.conn:
            return []
        try:
            mdx = f"SELECT * FROM $system.MDSCHEMA_MEASURES WHERE CUBE_NAME = '{cube_name}'"
            measures = [row.MEASURE_NAME for row in self.conn.cursor().execute(mdx)]
            
            mdx = f"SELECT * FROM $system.MDSCHEMA_DIMENSIONS WHERE CUBE_NAME = '{cube_name}'"
            dimensions = [row.DIMENSION_UNIQUE_NAME for row in self.conn.cursor().execute(mdx)]
            
            return measures + dimensions
        except Exception as e:
            print(f"Column error: {e}")
            return []

    def execute_query(self, mdx, max_rows=None):
        try:
            cursor = self.conn.cursor()
            cursor.execute(mdx)
            
            # Get column names
            columns = [col[0] for col in cursor.description]
            
            # Fetch data
            data = cursor.fetchmany(max_rows) if max_rows else cursor.fetchall()
            
            return columns, data
        except Exception as e:
            print(f"Query error: {e}")
            return [], []

class ExtractionThread(QThread):
    update_progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, cube_conn, cube_name, columns, start_date, end_date, db_path):
        super().__init__()
        self.cube_conn = cube_conn
        self.cube_name = cube_name
        self.columns = columns
        self.start_date = start_date
        self.end_date = end_date
        self.db_path = db_path
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            # Generate MDX query
            mdx_columns = ", ".join(self.columns)
            date_condition = f"[Date].[Date].&[{self.start_date}] : [Date].[Date].&[{self.end_date}]"
            mdx = f"SELECT {{ {mdx_columns} }} ON COLUMNS, NON EMPTY {{ {date_condition} }} ON ROWS FROM [{self.cube_name}]"

            # Connect to SQLite
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create table
            create_table = f"CREATE TABLE IF NOT EXISTS CubeData ({', '.join([f'[{col}] TEXT' for col in self.columns])})"
            cursor.execute(create_table)
            
            # Execute cube query
            cube_cursor = self.cube_conn.conn.cursor()
            cube_cursor.execute(mdx)
            
            # Process data in chunks
            chunk_size = 1000
            total_rows = 0
            
            while self._is_running:
                rows = cube_cursor.fetchmany(chunk_size)
                if not rows:
                    break
                
                # Insert into SQLite
                placeholders = ", ".join(["?"] * len(self.columns))
                insert_sql = f"INSERT INTO CubeData VALUES ({placeholders})"
                cursor.executemany(insert_sql, rows)
                conn.commit()
                
                total_rows += len(rows)
                self.update_progress.emit(total_rows, f"Extracted {total_rows} rows")
            
            conn.close()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class CubeExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSAS Cube Extractor")
        self.setGeometry(100, 100, 900, 700)
        
        # Settings
        self.settings = QSettings("CubeExtractor", "Settings")
        
        # Cube connection
        self.cube_conn = None
        self.extraction_thread = None
        
        # UI Setup
        self.init_ui()
        self.init_system_tray()
        
        # Load saved settings
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Connection Group
        conn_group = QGroupBox("Cube Connection")
        conn_layout = QVBoxLayout()
        
        # Server Input
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("Server:"))
        self.server_input = QLineEdit()
        server_layout.addWidget(self.server_input)
        conn_layout.addLayout(server_layout)
        
        # Database Input
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        self.db_input = QLineEdit()
        db_layout.addWidget(self.db_input)
        conn_layout.addLayout(db_layout)
        
        # Connect Button
        self.connect_btn = QPushButton("Connect to Cube")
        self.connect_btn.clicked.connect(self.connect_to_cube)
        conn_layout.addWidget(self.connect_btn)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # Cube Selection
        cube_layout = QHBoxLayout()
        cube_layout.addWidget(QLabel("Select Cube:"))
        self.cube_combo = QComboBox()
        self.cube_combo.currentIndexChanged.connect(self.load_cube_columns)
        cube_layout.addWidget(self.cube_combo)
        main_layout.addLayout(cube_layout)
        
        # Column Selection
        col_group = QGroupBox("Select Columns")
        col_layout = QVBoxLayout()
        
        self.column_list = QListWidget()
        self.column_list.setSelectionMode(QListWidget.MultiSelection)
        col_layout.addWidget(self.column_list)
        
        col_group.setLayout(col_layout)
        main_layout.addWidget(col_group)
        
        # Date Range
        date_layout = QHBoxLayout()
        date_layout.addWidget(QLabel("Start Date:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("End Date:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        date_layout.addWidget(self.end_date)
        main_layout.addLayout(date_layout)
        
        # Preview Section
        preview_btn = QPushButton("Preview Data (10 Rows)")
        preview_btn.clicked.connect(self.preview_data)
        main_layout.addWidget(preview_btn)
        
        self.preview_table = QTableView()
        main_layout.addWidget(self.preview_table)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_label = QLabel("Ready")
        main_layout.addWidget(self.progress_bar)
        main_layout.addWidget(self.progress_label)
        
        # Action Buttons
        btn_layout = QHBoxLayout()
        
        self.extract_btn = QPushButton("Start Extraction")
        self.extract_btn.clicked.connect(self.start_extraction)
        btn_layout.addWidget(self.extract_btn)
        
        self.stop_btn = QPushButton("Stop Extraction")
        self.stop_btn.clicked.connect(self.stop_extraction)
        self.stop_btn.setEnabled(False)
        btn_layout.addWidget(self.stop_btn)
        
        export_btn = QPushButton("Export to Excel")
        export_btn.clicked.connect(self.export_to_excel)
        btn_layout.addWidget(export_btn)
        
        main_layout.addLayout(btn_layout)
        
        # Scheduling
        sched_group = QGroupBox("Scheduling")
        sched_layout = QVBoxLayout()
        
        self.sched_check = QCheckBox("Enable Daily Extraction")
        sched_layout.addWidget(self.sched_check)
        
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("Extraction Time:"))
        self.time_combo = QComboBox()
        self.time_combo.addItems([f"{h:02d}:00" for h in range(24)])
        time_layout.addWidget(self.time_combo)
        sched_layout.addLayout(time_layout)
        
        sched_group.setLayout(sched_layout)
        main_layout.addWidget(sched_group)
        
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # Status Bar
        self.statusBar().showMessage("Ready")
        
        # Timer for scheduled extraction
        self.sched_timer = QTimer()
        self.sched_timer.timeout.connect(self.check_schedule)
        self.sched_timer.start(60000)  # Check every minute

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("icon.png"))
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

    def load_settings(self):
        # Load connection settings
        self.server_input.setText(self.settings.value("server", ""))
        self.db_input.setText(self.settings.value("database", ""))
        
        # Load scheduling settings
        self.sched_check.setChecked(self.settings.value("scheduling_enabled", False, type=bool))
        self.time_combo.setCurrentText(self.settings.value("extraction_time", "00:00"))
        
        # Load date range
        start_date = self.settings.value("start_date")
        end_date = self.settings.value("end_date")
        if start_date:
            self.start_date.setDate(QDate.fromString(start_date, Qt.ISODate))
        if end_date:
            self.end_date.setDate(QDate.fromString(end_date, Qt.ISODate))

    def save_settings(self):
        # Save connection settings
        self.settings.setValue("server", self.server_input.text())
        self.settings.setValue("database", self.db_input.text())
        
        # Save scheduling settings
        self.settings.setValue("scheduling_enabled", self.sched_check.isChecked())
        self.settings.setValue("extraction_time", self.time_combo.currentText())
        
        # Save date range
        self.settings.setValue("start_date", self.start_date.date().toString(Qt.ISODate))
        self.settings.setValue("end_date", self.end_date.date().toString(Qt.ISODate))

    def connect_to_cube(self):
        server = self.server_input.text()
        database = self.db_input.text()
        
        if not server or not database:
            QMessageBox.warning(self, "Input Error", "Please enter server and database names")
            return
        
        self.cube_conn = CubeConnection(server, database)
        
        # Try to connect with retry logic
        self.statusBar().showMessage("Connecting to cube...")
        QApplication.processEvents()
        
        if not self.retry_connection():
            QMessageBox.critical(self, "Connection Failed", "Could not connect to cube after multiple attempts")
            return
        
        # Load cubes
        self.cube_combo.clear()
        cubes = self.cube_conn.get_metadata()
        self.cube_combo.addItems(cubes)
        self.statusBar().showMessage(f"Connected to {server}/{database}")

    def retry_connection(self, max_attempts=10):
        for attempt in range(max_attempts):
            if self.cube_conn.connect():
                return True
            self.statusBar().showMessage(f"Connection failed. Retrying in 15 minutes... (Attempt {attempt+1}/{max_attempts})")
            QApplication.processEvents()
            QTimer.singleShot(900000, lambda: None)  # Wait 15 minutes
        return False

    def load_cube_columns(self):
        if not self.cube_conn or not self.cube_conn.conn:
            return
        
        cube_name = self.cube_combo.currentText()
        if not cube_name:
            return
        
        self.column_list.clear()
        columns = self.cube_conn.get_columns(cube_name)
        self.column_list.addItems(columns)

    def preview_data(self):
        if not self.validate_selection():
            return
        
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Generate MDX query
        mdx_columns = ", ".join(selected_cols)
        date_condition = f"[Date].[Date].&[{start_date}] : [Date].[Date].&[{end_date}]"
        mdx = f"SELECT TOP 10 {{ {mdx_columns} }} ON COLUMNS, {{ {date_condition} }} ON ROWS FROM [{cube_name}]"
        
        # Execute query
        columns, data = self.cube_conn.execute_query(mdx)
        
        # Display in table
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(columns)
        
        for row in data:
            items = [QStandardItem(str(item)) for item in row]
            model.appendRow(items)
        
        self.preview_table.setModel(model)
        self.preview_table.resizeColumnsToContents()

    def validate_selection(self):
        if not self.cube_conn or not self.cube_conn.conn:
            QMessageBox.warning(self, "Connection Error", "Not connected to cube")
            return False
        
        if not self.cube_combo.currentText():
            QMessageBox.warning(self, "Selection Error", "No cube selected")
            return False
        
        if not self.column_list.selectedItems():
            QMessageBox.warning(self, "Selection Error", "No columns selected")
            return False
        
        if self.start_date.date() > self.end_date.date():
            QMessageBox.warning(self, "Date Error", "Start date cannot be after end date")
            return False
        
        return True

    def start_extraction(self):
        if not self.validate_selection():
            return
        
        # Get output path
        db_path, _ = QFileDialog.getSaveFileName(self, "Save SQLite Database", "", "SQLite Databases (*.db)")
        if not db_path:
            return
        
        # Get parameters
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Setup extraction thread
        self.extraction_thread = ExtractionThread(
            self.cube_conn,
            cube_name,
            selected_cols,
            start_date,
            end_date,
            db_path
        )
        
        # Connect signals
        self.extraction_thread.update_progress.connect(self.update_progress)
        self.extraction_thread.finished.connect(self.extraction_finished)
        self.extraction_thread.error.connect(self.show_error)
        
        # Update UI
        self.extract_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting extraction...")
        
        # Start thread
        self.extraction_thread.start()

    def stop_extraction(self):
        if self.extraction_thread:
            self.extraction_thread.stop()
            self.extraction_thread.wait()
            self.progress_label.setText("Extraction stopped by user")

    def extraction_finished(self):
        self.extract_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_label.setText("Extraction completed successfully")
        QMessageBox.information(self, "Success", "Data extraction completed!")

    def update_progress(self, rows, message):
        self.progress_bar.setValue(rows % 100)  # Simple progress indicator
        self.progress_label.setText(message)

    def show_error(self, message):
        QMessageBox.critical(self, "Extraction Error", message)
        self.extract_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.progress_label.setText("Extraction failed")

    def export_to_excel(self):
        if not self.validate_selection():
            return
        
        # Get output path
        excel_path, _ = QFileDialog.getSaveFileName(self, "Save Excel File", "", "Excel Files (*.xlsx)")
        if not excel_path:
            return
        
        # Get parameters
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Generate MDX query
        mdx_columns = ", ".join(selected_cols)
        date_condition = f"[Date].[Date].&[{start_date}] : [Date].[Date].&[{end_date}]"
        mdx = f"SELECT {{ {mdx_columns} }} ON COLUMNS, {{ {date_condition} }} ON ROWS FROM [{cube_name}]"
        
        # Execute query
        columns, data = self.cube_conn.execute_query(mdx)
        
        # Create DataFrame
        df = pd.DataFrame(data, columns=columns)
        
        # Save to Excel
        try:
            df.to_excel(excel_path, index=False)
            QMessageBox.information(self, "Success", f"Data exported to {excel_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

    def check_schedule(self):
        if not self.sched_check.isChecked():
            return
        
        current_time = datetime.now().strftime("%H:%M")
        scheduled_time = self.time_combo.currentText()
        
        if current_time == scheduled_time:
            self.start_extraction()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CubeExtractorApp()
    window.show()
    sys.exit(app.exec_())