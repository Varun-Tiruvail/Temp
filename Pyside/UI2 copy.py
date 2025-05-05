# feedback_app.py - Updated with Approval System
import sqlite3
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import hashlib

class FeedbackDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('feedback.db')
        self.create_tables()
        
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                encrypted_data TEXT NOT NULL,
                approved BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        self.conn.commit()
        
    def create_user(self, username, password):
        encryption_key = hashlib.sha256(password.encode()).digest()
        iv = get_random_bytes(AES.block_size)
        cipher = AES.new(encryption_key, AES.MODE_CBC, iv)
        ct_bytes = cipher.encrypt(pad(password.encode(), AES.block_size))
        encrypted_data = base64.b64encode(iv + ct_bytes).decode()
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO users (username, encrypted_data, approved)
            VALUES (?, ?, ?)
        ''', (username, encrypted_data, False))
        self.conn.commit()
        
    def validate_user(self, username, password):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT encrypted_data FROM users WHERE username = ?
        ''', (username,))
        result = cursor.fetchone()
        
        if not result:
            return False
            
        try:
            encryption_key = hashlib.sha256(password.encode()).digest()
            encrypted_data = base64.b64decode(result[0])
            iv = encrypted_data[:AES.block_size]
            ct = encrypted_data[AES.block_size:]
            
            cipher = AES.new(encryption_key, AES.MODE_CBC, iv=iv)
            pt = unpad(cipher.decrypt(ct), AES.block_size).decode()
            return pt == password
        except (ValueError, KeyError):
            return False

    def get_unapproved_reportees(self, usernames):
        cursor = self.conn.cursor()
        placeholders = ','.join(['?']*len(usernames))
        cursor.execute(f'''
            SELECT username FROM users 
            WHERE username IN ({placeholders}) AND approved = 0
        ''', usernames)
        return [row[0] for row in cursor.fetchall()]

    def approve_users(self, usernames):
        cursor = self.conn.cursor()
        placeholders = ','.join(['?']*len(usernames))
        cursor.execute(f'''
            UPDATE users SET approved = 1 
            WHERE username IN ({placeholders})
        ''', usernames)
        self.conn.commit()
    
    def get_user_status(self, username):
        cursor = self.conn.cursor()
        cursor.execute('SELECT approved FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        return result[0] if result else None

    def get_all_unapproved(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT username FROM users WHERE approved = 0')
        return [row[0] for row in cursor.fetchall()]

class HierarchyValidator:
    @staticmethod
    def validate_username(username):
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        cursor.execute('SELECT name FROM employees WHERE name = ?', (username,))
        result = cursor.fetchone()
        conn.close()
        return bool(result)
    
    @staticmethod
    def get_manager_reportees(manager_username):
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT e.name FROM employees e
            JOIN employees m ON e.manager_id = m.id
            WHERE m.name = ?
        ''', (manager_username,))
        reportees = [row[0] for row in cursor.fetchall()]
        conn.close()
        return reportees
    
    @staticmethod

    def get_hierarchy():
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, manager_id FROM employees')
        employees = cursor.fetchall()
        conn.close()
        return employees

class RegistrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("User Registration")
        self.setFixedSize(300, 200)
        
        layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_input = QLineEdit()
        self.confirm_input.setEchoMode(QLineEdit.Password)
        
        form_layout = QFormLayout()
        form_layout.addRow("Username:", self.username_input)
        form_layout.addRow("Password:", self.password_input)
        form_layout.addRow("Confirm Password:", self.confirm_input)
        
        self.register_btn = QPushButton("Register")
        self.register_btn.clicked.connect(self.validate_registration)
        
        layout.addLayout(form_layout)
        layout.addWidget(self.register_btn)
        self.setLayout(layout)

    def validate_registration(self):
        username = self.username_input.text()
        password = self.password_input.text()
        confirm = self.confirm_input.text()
        
        if not all([username, password, confirm]):
            QMessageBox.warning(self, "Error", "All fields are required")
            return
            
        if password != confirm:
            QMessageBox.warning(self, "Error", "Passwords do not match")
            return
            
        if not HierarchyValidator.validate_username(username):
            self.parent().show_hierarchy_error(username)
            self.reject()
            return
            
        try:
            self.parent().feedback_db.create_user(username, password)
            QMessageBox.information(self, "Success", "Registration submitted for approval")
            self.accept()
        except sqlite3.IntegrityError:
            QMessageBox.critical(self, "Error", "Username already exists")

class ApprovalDialog(QDialog):
    def __init__(self, users, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Approve Users")
        self.setFixedSize(300, 200)
        
        layout = QVBoxLayout()
        self.checkboxes = []
        
        for user in users:
            cb = QCheckBox(user)
            self.checkboxes.append(cb)
            layout.addWidget(cb)
        
        approve_btn = QPushButton("Approve Selected")
        approve_btn.clicked.connect(self.approve_selected)
        layout.addWidget(approve_btn)
        
        self.setLayout(layout)

    def approve_selected(self):
        selected = [cb.text() for cb in self.checkboxes if cb.isChecked()]
        if selected:
            self.parent().feedback_db.approve_users(selected)
            QMessageBox.information(self, "Success", f"Approved {len(selected)} users")
            self.accept()

class FeedbackLoginWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.feedback_db = FeedbackDatabase()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Feedback System Login')
        self.setGeometry(300, 300, 400, 250)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        
        login_btn = QPushButton('Login')
        register_label = QLabel('<a href="register">Don\'t have an account? Register</a>')
        register_label.setOpenExternalLinks(False)
        register_label.linkActivated.connect(self.show_registration)
        
        layout.addWidget(QLabel('Username:'))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel('Password:'))
        layout.addWidget(self.password_input)
        layout.addWidget(login_btn)
        layout.addWidget(register_label)
        
        login_btn.clicked.connect(self.login)

    def show_registration(self):
        dialog = RegistrationDialog(self)
        dialog.exec()

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_error("Please enter both username and password")
            return
            
        if self.feedback_db.validate_user(username, password):
            # Check if manager has reportees to approve
            reportees = HierarchyValidator.get_manager_reportees(username)
            if reportees:
                unapproved = self.feedback_db.get_unapproved_reportees(reportees)
                if unapproved:
                    approval_dialog = ApprovalDialog(unapproved, self)
                    approval_dialog.exec()
            
            self.open_feedback_interface(username)
        else:
            self.show_error("Invalid credentials")
    def show_hierarchy_error(self, username):
        dialog = QDialog(self)
        dialog.setWindowTitle('Validation Error')
        layout = QVBoxLayout(dialog)
        
        layout.addWidget(QLabel(f'Username "{username}" not found in hierarchy!'))
        layout.addWidget(QLabel('Current Organization Hierarchy:'))
        
        tree = QTreeView()
        model = QStandardItemModel()
        model.setHorizontalHeaderLabels(['Name'])
        
        employees = HierarchyValidator.get_hierarchy()
        employee_map = {emp[0]: QStandardItem(emp[1]) for emp in employees}
        
        for emp in employees:
            if emp[2] is None:  # emp[2] is manager_id
                model.appendRow(employee_map[emp[0]])
            else:
                if emp[2] in employee_map:
                    employee_map[emp[2]].appendRow(employee_map[emp[0]])
        
        tree.setModel(model)
        layout.addWidget(tree)
        layout.addWidget(QLabel('Contact Tech Team if this is incorrect'))
        dialog.exec()

    def open_feedback_interface(self, username):
        self.feedback_window = FeedbackMainWindow(username)
        self.feedback_window.show()
        self.close()

    def show_error(self, message):
        QMessageBox.critical(self, 'Error', message)

class FeedbackMainWindow(QMainWindow):
    def __init__(self, username):
        super().__init__()
        self.username = username
        self.feedback_db = FeedbackDatabase()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f'Feedback System - Welcome {self.username}')
        self.setGeometry(100, 100, 800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # Feedback Input
        self.feedback_input = QTextEdit()
        submit_btn = QPushButton('Submit Feedback')
        
        # Previous Feedback
        self.feedback_list = QListWidget()
        
        # Approval status indicator
        self.approval_label = QLabel()
        self.update_approval_status()
        
        layout.addWidget(QLabel('Your Feedback:'))
        layout.addWidget(self.feedback_input)
        layout.addWidget(submit_btn)
        layout.addWidget(QLabel('Previous Feedback:'))
        layout.addWidget(self.feedback_list)
        layout.addWidget(self.approval_label)
        
        submit_btn.clicked.connect(self.submit_feedback)
        self.load_previous_feedback()

    def update_approval_status(self):
        approved = self.feedback_db.get_user_status(self.username)
        status = "Approved" if approved else "Pending Approval"
        self.approval_label.setText(f"Account Status: {status}")

    def submit_feedback(self):
        feedback = self.feedback_input.toPlainText()
        if not feedback:
            QMessageBox.warning(self, 'Warning', 'Cannot submit empty feedback')
            return
            
        # Here you would add code to actually store the feedback
        QMessageBox.information(self, 'Success', 'Feedback submitted!')
        self.feedback_input.clear()

    def load_previous_feedback(self):
        # Here you would load actual feedback from database
        self.feedback_list.addItems([
            "Sample feedback 1 - Pending review",
            "Sample feedback 2 - Approved"
        ])

if __name__ == '__main__':
    app = QApplication([])
    window = FeedbackLoginWindow()
    window.show()
    app.exec()