import os
import sys
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                              QPushButton, QComboBox, QListWidget, QDateEdit, QTableView, QCheckBox, QGroupBox,
                              QMessageBox, QFileDialog, QAbstractItemView, QProgressBar, QSystemTrayIcon, QMenu,
                              QAction, QListWidgetItem)
from PySide6.QtCore import Qt, QTimer, QThread, Signal, QSettings, QDate, QTime
from PySide6.QtGui import QStandardItemModel, QStandardItem, QIcon
import pyadomd

class CubeConnection:
    def __init__(self, server, database):
        self.connection_string = f"Provider=MSOLAP;Data Source={server};Initial Catalog={database};Integrated Security=SSPI;"
        self.conn = None
        self.server = server
        self.database = database

    def connect(self):
        try:
            if self.conn:
                self.conn.close()
            self.conn = pyadomd.Pyadomd(self.connection_string)
            self.conn.open()
            return True
        except Exception as e:
            print(f"Connection error: {e}")
            return False

    def disconnect(self):
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
            finally:
                self.conn = None

    def get_metadata(self):
        if not self.conn:
            return []
        try:
            # Get cubes using DMV query
            query = "SELECT CUBE_NAME FROM $system.MDSCHEMA_CUBES WHERE CUBE_SOURCE = 1"
            cursor = self.conn.cursor()
            cursor.execute(query)
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Metadata error: {e}")
            return []

    def get_columns(self, cube_name):
        if not self.conn:
            return []
        try:
            # Get measures
            measures_query = f"""
                SELECT [MEASURE_NAME] 
                FROM $system.MDSCHEMA_MEASURES 
                WHERE CUBE_NAME = '{cube_name}'
            """
            cursor = self.conn.cursor()
            cursor.execute(measures_query)
            measures = [row[0] for row in cursor.fetchall()]
            
            # Get dimensions
            dimensions_query = f"""
                SELECT [DIMENSION_UNIQUE_NAME] 
                FROM $system.MDSCHEMA_DIMENSIONS 
                WHERE CUBE_NAME = '{cube_name}' 
                  AND DIMENSION_TYPE <> 2
            """
            cursor.execute(dimensions_query)
            dimensions = [row[0] for row in cursor.fetchall()]
            
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
            if max_rows:
                data = cursor.fetchmany(max_rows)
            else:
                data = cursor.fetchall()
            
            return columns, data
        except Exception as e:
            print(f"Query error: {e}")
            return [], []

class ExtractionThread(QThread):
    update_progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, server, database, cube_name, columns, start_date, end_date, db_path):
        super().__init__()
        self.server = server
        self.database = database
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
            # Create SQLite connection
            sqlite_conn = sqlite3.connect(self.db_path)
            cursor = sqlite_conn.cursor()
            
            # Create table with sanitized column names
            safe_columns = [f'"{col.replace(".", "_").replace(" ", "_")}"' for col in self.columns]
            create_table = f"CREATE TABLE IF NOT EXISTS CubeData ({', '.join([f'{col} TEXT' for col in safe_columns])})"
            cursor.execute(create_table)
            sqlite_conn.commit()
            
            # Create cube connection
            cube_conn = CubeConnection(self.server, self.database)
            if not cube_conn.connect():
                raise Exception("Failed to connect to cube")
            
            # Generate MDX query
            mdx_columns = ", ".join([f"[{col}]" for col in self.columns])
            date_condition = f"[Date].[Date].&[{self.start_date}] : [Date].[Date].&[{self.end_date}]"
            mdx = f"""
                SELECT {{ {mdx_columns} }} ON COLUMNS, 
                NON EMPTY {{ {date_condition} }} ON ROWS 
                FROM [{self.cube_name}]
            """
            
            # Execute query
            cube_cursor = cube_conn.conn.cursor()
            cube_cursor.execute(mdx)
            
            # Process data in chunks
            chunk_size = 5000
            total_rows = 0
            placeholders = ", ".join(["?"] * len(self.columns))
            insert_sql = f"INSERT INTO CubeData VALUES ({placeholders})"
            
            while self._is_running:
                rows = cube_cursor.fetchmany(chunk_size)
                if not rows:
                    break
                
                # Insert into SQLite
                cursor.executemany(insert_sql, rows)
                sqlite_conn.commit()
                
                total_rows += len(rows)
                self.update_progress.emit(total_rows, f"Extracted {total_rows} rows")
            
            sqlite_conn.close()
            cube_conn.disconnect()
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class CubeExtractorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSAS Cube Extractor")
        self.setGeometry(100, 100, 1000, 800)
        
        # Settings
        self.settings = QSettings("CubeExtractor", "Settings")
        
        # Cube connection
        self.cube_conn = None
        self.extraction_thread = None
        self.connection_timer = QTimer()
        self.connection_timer.timeout.connect(self.check_connection)
        
        # UI Setup
        self.init_ui()
        self.init_system_tray()
        
        # Load saved settings
        self.load_settings()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # Connection Group
        conn_group = QGroupBox("Cube Connection")
        conn_layout = QVBoxLayout()
        conn_layout.setSpacing(8)
        
        # Server Input
        server_layout = QHBoxLayout()
        server_layout.addWidget(QLabel("Server:"))
        self.server_input = QLineEdit()
        self.server_input.setPlaceholderText("e.g. myserver\\instance")
        server_layout.addWidget(self.server_input, 1)
        conn_layout.addLayout(server_layout)
        
        # Database Input
        db_layout = QHBoxLayout()
        db_layout.addWidget(QLabel("Database:"))
        self.db_input = QLineEdit()
        self.db_input.setPlaceholderText("SSAS database name")
        db_layout.addWidget(self.db_input, 1)
        conn_layout.addLayout(db_layout)
        
        # Connect Button
        self.connect_btn = QPushButton("Connect to Cube")
        self.connect_btn.clicked.connect(self.connect_to_cube)
        conn_layout.addWidget(self.connect_btn)
        
        # Connection Status
        self.connection_status = QLabel("Not connected")
        self.connection_status.setStyleSheet("color: gray; font-weight: bold;")
        conn_layout.addWidget(self.connection_status)
        
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)
        
        # Cube Selection
        cube_layout = QHBoxLayout()
        cube_layout.addWidget(QLabel("Select Cube:"))
        self.cube_combo = QComboBox()
        self.cube_combo.setMinimumWidth(200)
        self.cube_combo.currentIndexChanged.connect(self.load_cube_columns)
        cube_layout.addWidget(self.cube_combo, 1)
        main_layout.addLayout(cube_layout)
        
        # Column Selection
        col_group = QGroupBox("Select Columns (Double-click to select/deselect all)")
        col_layout = QVBoxLayout()
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.select_all_columns)
        col_layout.addWidget(self.select_all_btn)
        
        self.column_list = QListWidget()
        self.column_list.setSelectionMode(QListWidget.MultiSelection)
        self.column_list.itemDoubleClicked.connect(self.toggle_select_all)
        col_layout.addWidget(self.column_list)
        
        col_group.setLayout(col_layout)
        main_layout.addWidget(col_group)
        
        # Date Range
        date_group = QGroupBox("Date Range")
        date_layout = QHBoxLayout()
        
        date_layout.addWidget(QLabel("Start Date:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-6))
        date_layout.addWidget(self.start_date)
        
        date_layout.addWidget(QLabel("End Date:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        date_layout.addWidget(self.end_date)
        
        date_group.setLayout(date_layout)
        main_layout.addWidget(date_group)
        
        # Preview Section
        preview_group = QGroupBox("Data Preview")
        preview_layout = QVBoxLayout()
        
        preview_btn_layout = QHBoxLayout()
        self.preview_btn = QPushButton("Preview Data (First 10 Rows)")
        self.preview_btn.clicked.connect(self.preview_data)
        preview_btn_layout.addWidget(self.preview_btn)
        
        self.skip_preview_check = QCheckBox("Skip preview if connection fails")
        self.skip_preview_check.setChecked(True)
        preview_btn_layout.addWidget(self.skip_preview_check)
        preview_layout.addLayout(preview_btn_layout)
        
        self.preview_table = QTableView()
        self.preview_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        preview_layout.addWidget(self.preview_table)
        
        preview_group.setLayout(preview_layout)
        main_layout.addWidget(preview_group)
        
        # Progress Section
        progress_group = QGroupBox("Extraction Progress")
        progress_layout = QVBoxLayout()
        
        self.progress_label = QLabel("Ready")
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # Action Buttons
        action_group = QGroupBox("Actions")
        action_layout = QHBoxLayout()
        
        self.extract_btn = QPushButton("Start Extraction")
        self.extract_btn.clicked.connect(self.start_extraction)
        action_layout.addWidget(self.extract_btn)
        
        self.stop_btn = QPushButton("Stop Extraction")
        self.stop_btn.clicked.connect(self.stop_extraction)
        self.stop_btn.setEnabled(False)
        action_layout.addWidget(self.stop_btn)
        
        self.export_btn = QPushButton("Export to Excel")
        self.export_btn.clicked.connect(self.export_to_excel)
        action_layout.addWidget(self.export_btn)
        
        action_group.setLayout(action_layout)
        main_layout.addWidget(action_group)
        
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
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")
        
        # Timer for scheduled extraction
        self.sched_timer = QTimer()
        self.sched_timer.timeout.connect(self.check_schedule)
        self.sched_timer.start(60000)  # Check every minute

    def init_system_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromTheme("document-save"))
        
        tray_menu = QMenu()
        show_action = tray_menu.addAction("Show")
        show_action.triggered.connect(self.show)
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(QApplication.quit)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        self.save_settings()
        self.stop_extraction()
        if self.cube_conn:
            self.cube_conn.disconnect()
        event.accept()

    def load_settings(self):
        # Load connection settings
        self.server_input.setText(self.settings.value("server", ""))
        self.db_input.setText(self.settings.value("database", ""))
        
        # Load scheduling settings
        self.sched_check.setChecked(self.settings.value("scheduling_enabled", False, type=bool))
        self.time_combo.setCurrentText(self.settings.value("extraction_time", "02:00"))
        
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
        server = self.server_input.text().strip()
        database = self.db_input.text().strip()
        
        if not server or not database:
            QMessageBox.warning(self, "Input Error", "Please enter server and database names")
            return
        
        if not self.cube_conn or self.cube_conn.server != server or self.cube_conn.database != database:
            if self.cube_conn:
                self.cube_conn.disconnect()
            self.cube_conn = CubeConnection(server, database)
        
        self.status_bar.showMessage("Connecting to cube...")
        QApplication.processEvents()
        
        if self.cube_conn.connect():
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.status_bar.showMessage("Connection successful")
            
            # Load cubes
            self.cube_combo.clear()
            cubes = self.cube_conn.get_metadata()
            if cubes:
                self.cube_combo.addItems(cubes)
            else:
                self.status_bar.showMessage("No cubes found in database")
        else:
            self.connection_status.setText("Connection failed - retrying...")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.status_bar.showMessage("Connection failed, will retry every 15 minutes")
            self.connection_timer.start(900000)  # 15 minutes

    def check_connection(self):
        if self.cube_conn and self.cube_conn.connect():
            self.connection_timer.stop()
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            self.status_bar.showMessage("Reconnected successfully")
            
            # Reload cubes
            self.cube_combo.clear()
            cubes = self.cube_conn.get_metadata()
            if cubes:
                self.cube_combo.addItems(cubes)
        else:
            self.status_bar.showMessage(f"Retry failed at {datetime.now().strftime('%H:%M')}, will try again in 15 min")

    def load_cube_columns(self):
        if not self.cube_conn or not self.cube_conn.conn:
            return
        
        cube_name = self.cube_combo.currentText()
        if not cube_name:
            return
        
        self.column_list.clear()
        columns = self.cube_conn.get_columns(cube_name)
        if columns:
            self.column_list.addItems(columns)
        else:
            self.status_bar.showMessage(f"No columns found for cube: {cube_name}")

    def toggle_select_all(self):
        if self.column_list.count() == 0:
            return
        
        # Toggle selection state
        all_selected = all(self.column_list.item(i).isSelected() for i in range(self.column_list.count()))
        for i in range(self.column_list.count()):
            self.column_list.item(i).setSelected(not all_selected)

    def select_all_columns(self):
        for i in range(self.column_list.count()):
            self.column_list.item(i).setSelected(True)

    def preview_data(self):
        if not self.validate_selection():
            return
        
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Generate MDX query
        mdx_columns = ", ".join([f"[{col}]" for col in selected_cols])
        date_condition = f"[Date].[Date].&[{start_date}] : [Date].[Date].&[{end_date}]"
        mdx = f"""
            SELECT TOP 10 {{ {mdx_columns} }} ON COLUMNS, 
            NON EMPTY {{ {date_condition} }} ON ROWS 
            FROM [{cube_name}]
        """
        
        try:
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
            self.status_bar.showMessage(f"Preview loaded: {len(data)} rows")
        except Exception as e:
            if not self.skip_preview_check.isChecked():
                QMessageBox.warning(self, "Preview Error", f"Failed to load preview: {str(e)}")
            self.status_bar.showMessage(f"Preview failed: {str(e)}")

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
        default_name = f"{self.cube_combo.currentText()}_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
        db_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save SQLite Database", 
            os.path.join(os.getcwd(), default_name),
            "SQLite Databases (*.db)"
        )
        if not db_path:
            return
        
        # Get parameters
        server = self.server_input.text().strip()
        database = self.db_input.text().strip()
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Setup extraction thread
        self.extraction_thread = ExtractionThread(
            server,
            database,
            cube_name,
            selected_cols,
            start_date,
            end_date,
            db_path
        )
        
        # Connect signals
        self.extraction_thread.update_progress.connect(self.update_progress)
        self.extraction_thread.finished.connect(self.extraction_finished)
        self.extraction_thread.error.connect(self.show_extraction_error)
        
        # Update UI
        self.extract_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.export_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("Starting extraction...")
        
        # Start thread
        self.extraction_thread.start()
        self.status_bar.showMessage("Extraction started")

    def stop_extraction(self):
        if self.extraction_thread and self.extraction_thread.isRunning():
            self.extraction_thread.stop()
            self.extraction_thread.wait()
            self.progress_label.setText("Extraction stopped by user")
            self.status_bar.showMessage("Extraction stopped")

    def extraction_finished(self):
        self.extract_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        self.progress_label.setText("Extraction completed successfully")
        self.status_bar.showMessage("Data extraction completed")
        QMessageBox.information(self, "Success", "Data extraction completed!")

    def update_progress(self, rows, message):
        # Simple progress indicator
        progress = min(100, rows // 1000)
        self.progress_bar.setValue(progress)
        self.progress_label.setText(message)

    def show_extraction_error(self, message):
        QMessageBox.critical(self, "Extraction Error", message)
        self.extract_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.export_btn.setEnabled(True)
        self.progress_label.setText("Extraction failed")
        self.status_bar.showMessage(f"Extraction failed: {message}")

    def export_to_excel(self):
        if not self.validate_selection():
            return
        
        # Get output path
        default_name = f"{self.cube_combo.currentText()}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        excel_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Excel File", 
            os.path.join(os.getcwd(), default_name),
            "Excel Files (*.xlsx)"
        )
        if not excel_path:
            return
        
        # Get parameters
        cube_name = self.cube_combo.currentText()
        selected_cols = [item.text() for item in self.column_list.selectedItems()]
        start_date = self.start_date.date().toString("yyyyMMdd")
        end_date = self.end_date.date().toString("yyyyMMdd")
        
        # Generate MDX query
        mdx_columns = ", ".join([f"[{col}]" for col in selected_cols])
        date_condition = f"[Date].[Date].&[{start_date}] : [Date].[Date].&[{end_date}]"
        mdx = f"""
            SELECT {{ {mdx_columns} }} ON COLUMNS, 
            NON EMPTY {{ {date_condition} }} ON ROWS 
            FROM [{cube_name}]
        """
        
        try:
            # Execute query
            columns, data = self.cube_conn.execute_query(mdx)
            
            if not data:
                QMessageBox.warning(self, "Export Error", "No data returned from cube")
                return
            
            # Create DataFrame
            df = pd.DataFrame(data, columns=columns)
            
            # Save to Excel
            df.to_excel(excel_path, index=False)
            QMessageBox.information(self, "Success", f"Data exported to {excel_path}")
            self.status_bar.showMessage(f"Data exported to {excel_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))
            self.status_bar.showMessage(f"Export failed: {str(e)}")

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