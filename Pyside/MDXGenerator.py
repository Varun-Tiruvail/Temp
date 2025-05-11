import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
                               QListWidget, QTextEdit, QDialog, QMessageBox, QLabel, QDialogButtonBox,QListWidgetItem)
from PySide6.QtCore import Qt
import pyadomd
import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
                               QListWidget, QTextEdit, QDialog, QMessageBox, QLabel, 
                               QDialogButtonBox, QCheckBox, QFileDialog, QMenu)

from PySide6.QtCore import Qt, QSize, QCursor

from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand, AdomdParameter

class AxisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Axis")
        layout = QVBoxLayout()
        
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Columns", "Rows", "Filters"])
        
        layout.addWidget(QLabel("Select axis:"))
        layout.addWidget(self.axis_combo)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.setLayout(layout)

class CodeDialog(QDialog):
    def __init__(self, code, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generated Python Code")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout()
        self.code_edit = QTextEdit()
        self.code_edit.setPlainText(code)
        self.code_edit.setReadOnly(True)
        
        save_btn = QPushButton("Save to File")
        save_btn.clicked.connect(self.save_code)
        
        layout.addWidget(self.code_edit)
        layout.addWidget(save_btn)
        self.setLayout(layout)
    
    def save_code(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Python File", "", "Python Files (*.py)")
        if path:
            with open(path, 'w') as f:
                f.write(self.code_edit.toPlainText())
            QMessageBox.information(self, "Saved", f"File saved to:\n{path}")

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MDX Query Builder")
        self.setGeometry(100, 100, 1200, 800)
        
        # UI Components
        self.connection_string = QLineEdit()
        self.connect_btn = QPushButton("Connect")
        self.cube_combo = QComboBox()
        self.metadata_tree = QTreeWidget()
        self.columns_list = QListWidget()
        self.rows_list = QListWidget()
        self.filters_list = QListWidget()
        self.query_edit = QTextEdit()
        self.non_empty_cols = QCheckBox("Non Empty Columns")
        self.non_empty_rows = QCheckBox("Non Empty Rows")
        self.export_btn = QPushButton("Export Python Code")
        
        # Layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        
        # Connection Section
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Connection String:"))
        top_layout.addWidget(self.connection_string)
        top_layout.addWidget(self.connect_btn)
        
        # Middle Section
        middle_layout = QHBoxLayout()
        
        # Left Panel
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Cubes:"))
        left_layout.addWidget(self.cube_combo)
        left_layout.addWidget(QLabel("Metadata:"))
        left_layout.addWidget(self.metadata_tree)
        
        # Right Panel
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Columns:"))
        right_layout.addWidget(self.columns_list)
        right_layout.addWidget(self.non_empty_cols)
        right_layout.addWidget(QLabel("Rows:"))
        right_layout.addWidget(self.rows_list)
        right_layout.addWidget(self.non_empty_rows)
        right_layout.addWidget(QLabel("Filters:"))
        right_layout.addWidget(self.filters_list)
        
        middle_layout.addLayout(left_layout, 60)
        middle_layout.addLayout(right_layout, 40)
        
        # Assemble Main Layout
        main_layout.addLayout(top_layout)
        main_layout.addLayout(middle_layout)
        main_layout.addWidget(QLabel("Generated MDX Query:"))
        main_layout.addWidget(self.query_edit)
        main_layout.addWidget(self.export_btn)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Connections
        self.connect_btn.clicked.connect(self.connect_to_olap)
        self.cube_combo.currentTextChanged.connect(self.load_cube_metadata)
        self.metadata_tree.itemDoubleClicked.connect(self.handle_item_double_click)
        self.export_btn.clicked.connect(self.generate_python_code)
        self.non_empty_cols.stateChanged.connect(self.generate_mdx)
        self.non_empty_rows.stateChanged.connect(self.generate_mdx)
        
        # Initialize
        self.connection = None
        self.metadata_tree.setHeaderLabel("Cube Structure")
        
        # Enable drag-drop and context menus
        self.columns_list.setDragDropMode(QListWidget.InternalMove)
        self.rows_list.setDragDropMode(QListWidget.InternalMove)
        self.filters_list.setDragDropMode(QListWidget.InternalMove)
        
        for lst in [self.columns_list, self.rows_list, self.filters_list]:
            lst.setContextMenuPolicy(Qt.CustomContextMenu)
            lst.customContextMenuRequested.connect(
                lambda pos, l=lst: self.show_list_context_menu(l))
    
    def show_list_context_menu(self, list_widget):
        menu = QMenu()
        remove_action = menu.addAction("Remove Item")
        remove_action.triggered.connect(lambda: self.remove_selected_item(list_widget))
        menu.exec(QCursor.pos())
    
    def remove_selected_item(self, list_widget):
        for item in list_widget.selectedItems():
            list_widget.takeItem(list_widget.row(item))
        self.generate_mdx()
                
    def connect_to_olap(self):
        conn_str = self.connection_string.text()
        try:
            self.connection = AdomdConnection(conn_str)
            self.connection.Open()
            self.load_cubes()
            QMessageBox.information(self, "Success", "Connected successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")

    def load_cubes(self):
        self.cube_combo.clear()
        try:
            cmd = AdomdCommand("SELECT CUBE_NAME FROM $system.MDSCHEMA_CUBES WHERE CUBE_TYPE = 'CUBE'", 
                            self.connection)
            reader = cmd.ExecuteReader()
            cubes = []
            try:
                while reader.Read():
                    cubes.append(reader.GetString(0))
            finally:
                reader.Close()
            self.cube_combo.addItems(cubes)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load cubes: {str(e)}")

    def load_cube_metadata(self, cube_name):
        self.metadata_tree.clear()
        if not cube_name:
            return

        try:
            # Escape single quotes in cube name
            safe_cube_name = cube_name.replace("'", "''")

            # Load dimensions and hierarchies
            hier_query = f"""
            SELECT [DIMENSION_UNIQUE_NAME], [HIERARCHY_UNIQUE_NAME], [HIERARCHY_CAPTION]
            FROM $system.MDSCHEMA_HIERARCHIES
            WHERE CUBE_NAME = '{safe_cube_name}' AND HIERARCHY_ORIGIN = 2
            """
            
            cmd = AdomdCommand(hier_query, self.connection)
            reader = cmd.ExecuteReader()
            dimensions = {}

            try:
                while reader.Read():
                    dim_name = reader.GetString(0)
                    hier_unique_name = reader.GetString(1)
                    hier_caption = reader.GetString(2)

                    if dim_name not in dimensions:
                        dimensions[dim_name] = QTreeWidgetItem(self.metadata_tree, [dim_name])
                    
                    hier_item = QTreeWidgetItem(dimensions[dim_name], [hier_caption])
                    hier_item.setData(0, Qt.UserRole, hier_unique_name)
                    hier_item.setData(0, Qt.UserRole + 1, "hierarchy")
            finally:
                reader.Close()

            # Load measures
            measures_query = f"""
            SELECT [MEASURE_UNIQUE_NAME], [MEASURE_NAME]
            FROM $system.MDSCHEMA_MEASURES
            WHERE CUBE_NAME = '{safe_cube_name}'
            """
            
            cmd = AdomdCommand(measures_query, self.connection)
            reader = cmd.ExecuteReader()
            measures_item = QTreeWidgetItem(self.metadata_tree, ["Measures"])
            
            try:
                while reader.Read():
                    measure_unique_name = reader.GetString(0)
                    measure_name = reader.GetString(1)
                    
                    measure_item = QTreeWidgetItem(measures_item, [measure_name])
                    measure_item.setData(0, Qt.UserRole, measure_unique_name)
                    measure_item.setData(0, Qt.UserRole + 1, "measure")
            finally:
                reader.Close()

            self.metadata_tree.expandAll()

        except Exception as e:
            QMessageBox.critical(
                self, 
                "Metadata Load Error",
                f"Failed to load cube metadata:\n{str(e)}"
            )
            
    def handle_item_double_click(self, item):
        unique_name = item.data(0, Qt.UserRole)
        item_type = item.data(0, Qt.UserRole+1)
        
        if not unique_name:
            return
        
        # Generate MDX expression based on item type
        if item_type == "hierarchy":
            mdx_expression = f"{unique_name}.Members"
        else:
            mdx_expression = unique_name
        
        dialog = AxisDialog(self)
        if dialog.exec():
            axis = dialog.axis_combo.currentText()
            target_list = {
                "Columns": self.columns_list,
                "Rows": self.rows_list,
                "Filters": self.filters_list
            }[axis]
            
            list_item = QListWidgetItem(mdx_expression)
            list_item.setData(Qt.UserRole, mdx_expression)
            target_list.addItem(list_item)
            self.generate_mdx()
   
    def generate_mdx(self):
        cube_name = self.cube_combo.currentText()
        columns = [self.columns_list.item(i).data(Qt.UserRole) 
                  for i in range(self.columns_list.count())]
        rows = [self.rows_list.item(i).data(Qt.UserRole) 
               for i in range(self.rows_list.count())]
        filters = [self.filters_list.item(i).data(Qt.UserRole) 
                  for i in range(self.filters_list.count())]

        select_clauses = []
        if columns:
            non_empty = "NON EMPTY " if self.non_empty_cols.isChecked() else ""
            select_clauses.append(f"{non_empty}{{ {', '.join(columns)} }} ON COLUMNS")
        if rows:
            non_empty = "NON EMPTY " if self.non_empty_rows.isChecked() else ""
            select_clauses.append(f"{non_empty}{{ {', '.join(rows)} }} ON ROWS")

        where_clause = ""
        if filters:
            where_clause = f"WHERE ( {', '.join(filters)} )"

        mdx = "SELECT\n    " + ",\n    ".join(select_clauses) + f"\nFROM [{cube_name}]"
        if where_clause:
            mdx += "\n" + where_clause
        
        self.query_edit.setPlainText(mdx)
        return mdx
    
    def generate_python_code(self):
        mdx_query = self.generate_mdx()
        conn_str = self.connection_string.text()
        
        code = f"""# Required DLL setup:
        # 1. Download Microsoft Analysis Services client libraries
        # 2. Place these DLLs in your Python environment's DLL search path:
        #    - Microsoft.AnalysisServices.AdomdClient.dll
        #    - Microsoft.AnalysisServices.AdomdClient.Xmla.dll
        #    - Microsoft.AnalysisServices.Core.dll

        import clr
        clr.AddReference('Microsoft.AnalysisServices.AdomdClient')

        from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand

        # Connection configuration
        connection_string = "{conn_str}"
        mdx_query = \"\"\"{mdx_query}\"\"\"

        def execute_mdx():
            conn = AdomdConnection(connection_string)
            try:
                conn.Open()
                cmd = AdomdCommand(mdx_query, conn)
                reader = cmd.ExecuteReader()
                
                # Get column headers
                columns = [col.ColumnName for col in reader.GetSchemaTable().Columns]
                print("|".join(columns))
                
                # Print results
                while reader.Read():
                    print("|".join(str(reader[i]) for i in range(len(columns))))
                    
            except Exception as e:
                print(f"Error")
            finally:
                conn.Close()

        if __name__ == "__main__":
            execute_mdx()
"""
        dialog = CodeDialog(code, self)
        dialog.exec()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())