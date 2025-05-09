import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
                               QListWidget, QTextEdit, QDialog, QMessageBox, QLabel, QDialogButtonBox,QListWidgetItem)
from PySide6.QtCore import Qt
import pyadomd
import System
from Microsoft.AnalysisServices.AdomdClient import AdomdConnection, AdomdCommand

class AxisDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Axis")
        layout = QVBoxLayout()
        self.label = QLabel("Select axis to add item:")
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        
        self.axis_combo = QComboBox()
        self.axis_combo.addItems(["Columns", "Rows", "Filters"])
        
        layout.addWidget(self.label)
        layout.addWidget(self.axis_combo)
        layout.addWidget(self.buttons)
        self.setLayout(layout)

        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

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
        
        # Layout
        central_widget = QWidget()
        main_layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Connection String:"))
        top_layout.addWidget(self.connection_string)
        top_layout.addWidget(self.connect_btn)
        
        middle_layout = QHBoxLayout()
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Cubes:"))
        left_layout.addWidget(self.cube_combo)
        left_layout.addWidget(QLabel("Metadata:"))
        left_layout.addWidget(self.metadata_tree)
        
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Columns:"))
        right_layout.addWidget(self.columns_list)
        right_layout.addWidget(QLabel("Rows:"))
        right_layout.addWidget(self.rows_list)
        right_layout.addWidget(QLabel("Filters:"))
        right_layout.addWidget(self.filters_list)
        
        middle_layout.addLayout(left_layout, 40)
        middle_layout.addLayout(right_layout, 20)
        
        main_layout.addLayout(top_layout)
        main_layout.addLayout(middle_layout)
        main_layout.addWidget(QLabel("Generated MDX Query:"))
        main_layout.addWidget(self.query_edit)
        
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        
        # Connections
        self.connect_btn.clicked.connect(self.connect_to_olap)
        self.cube_combo.currentTextChanged.connect(self.load_cube_metadata)
        self.metadata_tree.itemDoubleClicked.connect(self.handle_item_double_click)
        
        # Initialize
        self.connection = None
        self.metadata_tree.setHeaderLabel("Cube Structure")
    
            
    def connect_to_olap(self):
        conn_str = self.connection_string.text()
        try:
            self.connection = AdomdConnection(conn_str)
            self.connection.Open()
            self.load_cubes()
            QMessageBox.information(self, "Success", "Connected successfully!")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection failed: {str(e)}")
    
    # def load_cubes(self):
    #     self.cube_combo.clear()
    #     try:
    #         cmd = AdomdCommand("SELECT CUBE_NAME FROM $system.MDSCHEMA_CUBES WHERE CUBE_TYPE = 'CUBE'", 
    #                          self.connection)
    #         reader = cmd.ExecuteReader()
    #         cubes = []
    #         while reader.Read():
    #             cubes.append(reader.GetString(0))
    #         self.cube_combo.addItems(cubes)
    #         reader.Close()
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Failed to load cubes: {str(e)}")

    # def load_cube_metadata(self, cube_name):
    #     self.metadata_tree.clear()
    #     if not cube_name:
    #         return
        
    #     try:
    #         # Load dimensions and hierarchies
    #         cmd = AdomdCommand(f"""
    #             SELECT DIMENSION_UNIQUE_NAME, HIERARCHY_UNIQUE_NAME, HIERARCHY_CAPTION
    #             FROM $system.MDSCHEMA_HIERARCHIES
    #             WHERE CUBE_NAME = '{cube_name}' AND HIERARCHY_ORIGIN = 2
    #             """, self.connection)
    #         reader = cmd.ExecuteReader()
            
    #         dimensions = {}
    #         while reader.Read():
    #             dim_name = reader.GetString(0)
    #             hier_name = reader.GetString(1)
    #             hier_caption = reader.GetString(2)
                
    #             if dim_name not in dimensions:
    #                 dimensions[dim_name] = QTreeWidgetItem(self.metadata_tree, [dim_name])
                
    #             hier_item = QTreeWidgetItem(dimensions[dim_name], [hier_caption])
    #             hier_item.setData(0, Qt.UserRole, hier_name)
    #             hier_item.setData(0, Qt.UserRole+1, "hierarchy")
    #         reader.Close()

    #         # Load measures
    #         cmd = AdomdCommand(f"""
    #             SELECT MEASURE_UNIQUE_NAME, MEASURE_NAME
    #             FROM $system.MDSCHEMA_MEASURES
    #             WHERE CUBE_NAME = '{cube_name}'
    #             """, self.connection)
    #         reader = cmd.ExecuteReader()
            
    #         measures_item = QTreeWidgetItem(self.metadata_tree, ["Measures"])
    #         while reader.Read():
    #             measure_name = reader.GetString(1)
    #             measure_unique_name = reader.GetString(0)
    #             measure_item = QTreeWidgetItem(measures_item, [measure_name])
    #             measure_item.setData(0, Qt.UserRole, measure_unique_name)
    #             measure_item.setData(0, Qt.UserRole+1, "measure")
    #         reader.Close()
            
    #         self.metadata_tree.expandAll()
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Failed to load metadata: {str(e)}")

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

    # def load_cube_metadata(self, cube_name):
    #     self.metadata_tree.clear()
    #     if not cube_name:
    #         return
        
    #     try:
    #         # Load dimensions and hierarchies
    #         cmd = AdomdCommand(f"""
    #             SELECT DIMENSION_UNIQUE_NAME, HIERARCHY_UNIQUE_NAME, HIERARCHY_CAPTION
    #             FROM $system.MDSCHEMA_HIERARCHIES
    #             WHERE CUBE_NAME = '{cube_name}' AND HIERARCHY_ORIGIN = 2
    #             """, self.connection)
    #         reader = cmd.ExecuteReader()
    #         dimensions = {}
    #         try:
    #             while reader.Read():
    #                 dim_name = reader.GetString(0)
    #                 hier_name = reader.GetString(1)
    #                 hier_caption = reader.GetString(2)
                    
    #                 if dim_name not in dimensions:
    #                     dimensions[dim_name] = QTreeWidgetItem(self.metadata_tree, [dim_name])
                    
    #                 hier_item = QTreeWidgetItem(dimensions[dim_name], [hier_caption])
    #                 hier_item.setData(0, Qt.UserRole, hier_name)
    #                 hier_item.setData(0, Qt.UserRole+1, "hierarchy")
    #         finally:
    #             reader.Close()

    #         # Load measures
    #         cmd = AdomdCommand(f"""
    #             SELECT MEASURE_UNIQUE_NAME, MEASURE_NAME
    #             FROM $system.MDSCHEMA_MEASURES
    #             WHERE CUBE_NAME = '{cube_name}'
    #             """, self.connection)
    #         reader = cmd.ExecuteReader()
    #         measures_item = QTreeWidgetItem(self.metadata_tree, ["Measures"])
    #         try:
    #             while reader.Read():
    #                 measure_name = reader.GetString(1)
    #                 measure_unique_name = reader.GetString(0)
    #                 measure_item = QTreeWidgetItem(measures_item, [measure_name])
    #                 measure_item.setData(0, Qt.UserRole, measure_unique_name)
    #                 measure_item.setData(0, Qt.UserRole+1, "measure")
    #         finally:
    #             reader.Close()
            
    #         self.metadata_tree.expandAll()
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Failed to load metadata: {str(e)}")

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
        columns = [self.columns_list.item(i).data(Qt.UserRole) for i in range(self.columns_list.count())]
        rows = [self.rows_list.item(i).data(Qt.UserRole) for i in range(self.rows_list.count())]
        filters = [self.filters_list.item(i).data(Qt.UserRole) for i in range(self.filters_list.count())]
        
        select_clauses = []
        if columns:
            select_clauses.append(f"{{ {', '.join(columns)} }} ON COLUMNS")
        if rows:
            select_clauses.append(f"{{ {', '.join(rows)} }} ON ROWS")
        
        where_clause = ""
        if filters:
            where_clause = f"WHERE ( {', '.join(filters)} )"
        
        mdx = "SELECT\n    " + ",\n    ".join(select_clauses) + f"\nFROM [{cube_name}]"
        if where_clause:
            mdx += "\n" + where_clause
        
        self.query_edit.setPlainText(mdx)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())