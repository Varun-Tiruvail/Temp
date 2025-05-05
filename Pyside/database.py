import sqlite3
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

class EmployeeDatabase:
    
    def __init__(self):
        self.conn = sqlite3.connect('hierarchy.db')
        self.conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                position TEXT,
                manager_id INTEGER,
                FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL
            )
        ''')
        self.conn.commit()

    def add_employee(self, name, position, manager_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO employees (name, position, manager_id)
            VALUES (?, ?, ?)
        ''', (name, position, manager_id))
        self.conn.commit()
        return cursor.lastrowid

    def get_employees(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, name, position, manager_id FROM employees')
        return cursor.fetchall()

    def delete_employee(self, employee_id):
        cursor = self.conn.cursor()
        cursor.execute('DELETE FROM employees WHERE id = ?', (employee_id,))
        self.conn.commit()

    def update_employee(self, employee_id, name, position, manager_id=None):
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE employees 
            SET name = ?, position = ?, manager_id = ?
            WHERE id = ?
        ''', (name, position, manager_id, employee_id))
        self.conn.commit()

    def get_employee(self, employee_id):
        cursor = self.conn.cursor()
        cursor.execute('SELECT id, name, position, manager_id FROM employees WHERE id = ?', (employee_id,))
        return cursor.fetchone()

class HierarchyWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.db = EmployeeDatabase()
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setWindowTitle('Employee Hierarchy Manager')
        self.setGeometry(100, 100, 800, 600)

        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)

        # Tree View for hierarchy
        self.tree_view = QTreeView()
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(['Name', 'Position'])
        self.tree_view.setModel(self.model)
        layout.addWidget(self.tree_view)

        # Form for adding/editing employees
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        
        self.name_input = QLineEdit()
        self.position_input = QLineEdit()
        self.manager_combo = QComboBox()
        add_button = QPushButton('Add Employee')
        edit_button = QPushButton('Update Employee')
        delete_button = QPushButton('Delete Employee')

        form_layout.addWidget(QLabel('Name:'))
        form_layout.addWidget(self.name_input)
        form_layout.addWidget(QLabel('Position:'))
        form_layout.addWidget(self.position_input)
        form_layout.addWidget(QLabel('Manager:'))
        form_layout.addWidget(self.manager_combo)
        form_layout.addWidget(add_button)
        form_layout.addWidget(edit_button)
        form_layout.addWidget(delete_button)
        layout.addWidget(form_widget)

        # Connect signals
        add_button.clicked.connect(self.add_employee)
        edit_button.clicked.connect(self.update_employee)
        delete_button.clicked.connect(self.delete_employee)
        self.tree_view.selectionModel().selectionChanged.connect(self.load_employee_data)

    def load_data(self):
        self.model.clear()
        self.model.setHorizontalHeaderLabels(['Name', 'Position'])
        employees = self.db.get_employees()
        employee_dict = {}
        
        # First pass: create all items
        for emp in employees:
            item = QStandardItem(emp[1])
            item.setData(emp[0], Qt.ItemDataRole.UserRole)  # Store ID in item
            item.setData(emp[2], Qt.ItemDataRole.UserRole + 1)  # Store position
            employee_dict[emp[0]] = {
                'item': item,
                'manager_id': emp[3],
                'children': []
            }
        
        # Second pass: build hierarchy
        for emp_id, data in employee_dict.items():
            manager_id = data['manager_id']
            if manager_id in employee_dict:
                employee_dict[manager_id]['item'].appendRow(data['item'])
            else:
                self.model.appendRow(data['item'])
        
        self.update_manager_combo()

    def update_manager_combo(self):
        self.manager_combo.clear()
        self.manager_combo.addItem('None', None)
        for emp in self.db.get_employees():
            self.manager_combo.addItem(f"{emp[1]} ({emp[2]})", emp[0])

    def add_employee(self):
        name = self.name_input.text().strip()
        position = self.position_input.text().strip()
        manager_id = self.manager_combo.currentData()
        
        if not name:
            QMessageBox.warning(self, 'Warning', 'Name cannot be empty')
            return
            
        try:
            self.db.add_employee(name, position, manager_id)
            self.load_data()
            self.clear_form()
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, 'Error', f'Invalid manager selection: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Error adding employee: {str(e)}')

    def load_employee_data(self):
        indexes = self.tree_view.selectionModel().selectedIndexes()
        if not indexes:
            return
            
        index = indexes[0]
        item = self.model.itemFromIndex(index)
        self.selected_employee_id = item.data(Qt.ItemDataRole.UserRole)
        
        employee = self.db.get_employee(self.selected_employee_id)
        if employee:
            self.name_input.setText(employee[1])
            self.position_input.setText(employee[2])
            
            # Set manager combo
            manager_id = employee[3]
            index = self.manager_combo.findData(manager_id)
            self.manager_combo.setCurrentIndex(index if index != -1 else 0)

    def update_employee(self):
        if not self.selected_employee_id:
            QMessageBox.warning(self, 'Warning', 'Please select an employee to update')
            return
            
        name = self.name_input.text().strip()
        position = self.position_input.text().strip()
        manager_id = self.manager_combo.currentData()
        
        if not name:
            QMessageBox.warning(self, 'Warning', 'Name cannot be empty')
            return
            
        if manager_id == self.selected_employee_id:
            QMessageBox.warning(self, 'Invalid Manager', 'Employee cannot be their own manager')
            return
            
        try:
            self.db.update_employee(self.selected_employee_id, name, position, manager_id)
            self.load_data()
            self.clear_form()
            self.selected_employee_id = None
        except sqlite3.IntegrityError as e:
            QMessageBox.critical(self, 'Error', f'Invalid manager selection: {str(e)}')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Error updating employee: {str(e)}')

    def delete_employee(self):
        if not self.selected_employee_id:
            QMessageBox.warning(self, 'Warning', 'Please select an employee to delete')
            return
            
        reply = QMessageBox.question(
            self,
            'Confirm Delete',
            'Are you sure you want to delete this employee and remove them from all reporting chains?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.db.delete_employee(self.selected_employee_id)
                self.load_data()
                self.clear_form()
                self.selected_employee_id = None
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Error deleting employee: {str(e)}')

    def clear_form(self):
        self.name_input.clear()
        self.position_input.clear()
        self.manager_combo.setCurrentIndex(0)




if __name__ == '__main__':
    app = QApplication([])
    window = HierarchyWindow()
    window.show()
    app.exec()