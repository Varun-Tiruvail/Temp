# feedback_app.py - Updated with Approval System
from datetime import datetime
import json
import sqlite3
from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad
from Crypto.Random import get_random_bytes
import base64
import hashlib
from matplotlib import patheffects, pyplot as plt
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import os
import shutil
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

def get_onedrive_path():
    # Try different OneDrive environment variables
    paths = [
        os.getenv('OneDrive'),
        os.getenv('OneDriveCommercial'),
        Path.home() / 'OneDrive',
        Path.home() / 'OneDrive - Corporate'
    ]
    
    for path in paths:
        if path and Path(path).exists():
            return str(path)
    return None

def move_key_to_onedrive(username):
    onedrive_path = get_onedrive_path()
    if not onedrive_path:
        return False
    
    src = f"{username}.pem"
    dest = os.path.join(onedrive_path, f"{username}.pem")
    
    try:
        if os.path.exists(src):
            shutil.move(src, dest)
        return True
    except Exception as e:
        print(f"Key move failed: {str(e)}")
        return False



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
        # Create feedback responses table
        # cursor.execute('''
        #     CREATE TABLE IF NOT EXISTS feedback_responses (
        #         id INTEGER PRIMARY KEY AUTOINCREMENT,
        #         manager TEXT NOT NULL,
        #         reportee_type TEXT NOT NULL,
        #         question_id TEXT,
        #         response INTEGER,
        #         general_feedback TEXT,
        #         approval_status BOOLEAN NOT NULL,
        #         timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        #     )
        # ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manager TEXT NOT NULL,
                encrypted_data BLOB NOT NULL,
                approval_status BOOLEAN NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def username_exists(self, username):
        cursor = self.conn.cursor()
        cursor.execute('SELECT username FROM users WHERE username = ?', (username,))
        return cursor.fetchone() is not None

    def create_user(self, username, password):
        #check if username already exists
        if self.username_exists(username):
            raise ValueError("Username already exists")
        
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
    
    # In FeedbackDatabase class
    def get_user_status(self, username):
        cursor = self.conn.cursor()
        cursor.execute('SELECT approved FROM users WHERE username = ?', (username,))
        result = cursor.fetchone()
        return bool(result[0]) if result else False

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
    def get_manager_chain(username):
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        manager_chain = []
        current_user = username
        
        while True:
            cursor.execute('''
                SELECT m.name 
                FROM employees e
                JOIN employees m ON e.manager_id = m.id
                WHERE e.name = ?
            ''', (current_user,))
            result = cursor.fetchone()
            if not result:
                break
            manager_chain.append(result[0])
            current_user = result[0]
        
        conn.close()
        return manager_chain
    

    @staticmethod

    def get_hierarchy():
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, manager_id FROM employees')
        employees = cursor.fetchall()
        conn.close()
        return employees
    
    # Add to HierarchyValidator class
    @staticmethod
    def get_all_reportees(manager_username):
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        
        try:
            # Get manager ID
            cursor.execute('SELECT id FROM employees WHERE name = ?', (manager_username,))
            manager_id = cursor.fetchone()[0]
            
            # Recursive query to get all subordinates
            cursor.execute('''
                WITH RECURSIVE subordinates AS (
                    SELECT id, name, manager_id, 1 as level
                    FROM employees
                    WHERE manager_id = ?
                    UNION ALL
                    SELECT e.id, e.name, e.manager_id, s.level + 1
                    FROM employees e
                    INNER JOIN subordinates s ON e.manager_id = s.id
                )
                SELECT name, level FROM subordinates
            ''', (manager_id,))
            
            reportees = cursor.fetchall()
            direct = [name for name, level in reportees if level == 1]
            indirect = [name for name, level in reportees if level > 1]
            
            return direct, indirect
        except Exception as e:
            return [], []
        finally:
            conn.close()


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

        if self.parent().feedback_db.username_exists(username):
            QMessageBox.warning(self, "Error", "Username already registered")
            return
        
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
        
        direct, indirect = HierarchyValidator.get_all_reportees(username)
        if (len(direct) + len(indirect)) > 5:
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048
            )
            
            # Save private key with user's password
            pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.BestAvailableEncryption(
                    password.encode()
                )
            )
            with open(f"{username}.pem", "wb") as f:
                f.write(pem)
            
            # Save public key
            public_key = private_key.public_key()
            pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            with open(f"{username}_public.pem", "wb") as f:
                f.write(pem)

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

    # def login(self):
    #     username = self.username_input.text()
    #     password = self.password_input.text()
        
    #     if not username or not password:
    #         self.show_error("Please enter both username and password")
    #         return
        
    #     if self.feedback_db.validate_user(username, password):
    #         # Determine if user is a manager with enough reportees
    #         direct, indirect = HierarchyValidator.get_all_reportees(username)
    #         total_reportees = len(direct) + len(indirect)
    #         private_key = None

    #         if total_reportees > 5:
    #             onedrive_path = get_onedrive_path()
    #             if onedrive_path:
    #                 key_path = os.path.join(onedrive_path, f"{username}.pem")
    #                 public_key_path = f"{username}_public.pem"
                    
    #                 # Generate keys if not exists
    #                 if not os.path.exists(key_path) or not os.path.exists(public_key_path):
    #                     try:
    #                         # Generate new key pair
    #                         private_key = rsa.generate_private_key(
    #                             public_exponent=65537,
    #                             key_size=2048
    #                         )
    #                         # Encrypt and save private key
    #                         pem = private_key.private_bytes(
    #                             encoding=serialization.Encoding.PEM,
    #                             format=serialization.PrivateFormat.PKCS8,
    #                             encryption_algorithm=serialization.BestAvailableEncryption(password.encode())
    #                         )
    #                         with open(key_path, "wb") as f:
    #                             f.write(pem)
    #                         # Save public key
    #                         public_key = private_key.public_key()
    #                         public_pem = public_key.public_bytes(
    #                             encoding=serialization.Encoding.PEM,
    #                             format=serialization.PublicFormat.SubjectPublicKeyInfo
    #                         )
    #                         with open(public_key_path, "wb") as f:
    #                             f.write(public_pem)
    #                     except Exception as e:
    #                         QMessageBox.critical(self, "Key Error", f"Failed to generate keys: {str(e)}")
    #                         return
                    
    #                 # Load the private key
    #                 try:
    #                     with open(key_path, "rb") as f:
    #                         private_key = serialization.load_pem_private_key(
    #                             f.read(),
    #                             password=password.encode()
    #                         )
    #                 except Exception as e:
    #                     QMessageBox.critical(self, "Decryption Error", f"Failed to load private key: {str(e)}")
    #                     return

    #         # Proceed to open feedback interface with the private key
    #         self.open_feedback_interface(username, private_key)
            
    #         # Check for reportees needing approval
    #         reportees = HierarchyValidator.get_manager_reportees(username)
    #         if reportees:
    #             unapproved = self.feedback_db.get_unapproved_reportees(reportees)
    #             if unapproved:
    #                 approval_dialog = ApprovalDialog(unapproved, self)
    #                 approval_dialog.exec()
    #     else:
    #         self.show_error("Invalid credentials")


    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        
        if not username or not password:
            self.show_error("Please enter both username and password")
            return
        
        if self.feedback_db.validate_user(username, password):
            private_key = None
            key_path = f"{username}.pem"
            
            # Try to load private key
            if os.path.exists(key_path):
                try:
                    with open(key_path, "rb") as f:
                        private_key = serialization.load_pem_private_key(
                            f.read(),
                            password=password.encode()
                        )
                except Exception as e:
                    QMessageBox.warning(self, "Key Error",
                        f"Failed to load private key: {str(e)}")
            
            # Proceed to open feedback interface with the private key
            self.open_feedback_interface(username, private_key)
            
            # Check for reportees needing approval
            reportees = HierarchyValidator.get_manager_reportees(username)
            if reportees:
                unapproved = self.feedback_db.get_unapproved_reportees(reportees)
                if unapproved:
                    approval_dialog = ApprovalDialog(unapproved, self)
                    approval_dialog.exec()
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

    # def open_feedback_interface(self, username):
    #     self.feedback_window = FeedbackMainWindow(username)
    #     self.feedback_window.show()
    #     # self.close()
    #     self.hide()
    def open_feedback_interface(self, username, private_key=None):
        self.feedback_window = FeedbackMainWindow(username, private_key)
        self.feedback_window.show()
        self.hide()

    def show_error(self, message):
        QMessageBox.critical(self, 'Error', message)

# class FeedbackMainWindow(QMainWindow):
#     def __init__(self, username):
#         super().__init__()
#         self.username = username
#         self.feedback_db = FeedbackDatabase()
#         self.init_ui()

class FeedbackMainWindow(QMainWindow):
    def __init__(self, username, private_key=None):
        super().__init__()
        self.username = username
        self.private_key = private_key  # Store the private key
        self.feedback_db = FeedbackDatabase()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle(f'Feedback System - Welcome {self.username}')
        self.setGeometry(100, 100, 800, 600)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # Add visibility information
        visibility_info = self.create_visibility_info()
        layout.addWidget(visibility_info)
        
        # Previous Feedback
        self.feedback_list = QListWidget()
        
        # Approval status indicator
        self.approval_label = QLabel()
        self.update_approval_status()
        layout.addWidget(self.approval_label)
        # Add Survey Button
        hlayout=QHBoxLayout()
        feedback_btn = QPushButton('Give Feedback')
        feedback_btn.clicked.connect(self.open_survey)
        hlayout.addWidget(feedback_btn)

        self.analysis_btn = QPushButton('View Analysis')

        # Get reportee count
        direct, indirect = HierarchyValidator.get_all_reportees(self.username)
        self.total_reportees = len(direct) + len(indirect)
        
        # Only show button if total reportees > 5
        if self.total_reportees > 5:
            hlayout.addWidget(self.analysis_btn)
            self.analysis_btn.clicked.connect(self.check_feedback_before_analysis)
        else:
            hlayout.addWidget(QLabel("Analysis available with 6+ reportees"))
            
        # analysis_btn.clicked.connect(self.show_analysis)
        # layout.addWidget(analysis_btn)
        layout.addLayout(hlayout)
        # Add sign-out button to toolbar
        toolbar = self.addToolBar("Main Toolbar")
        signout_action = QAction(QIcon(), "Sign Out", self)
        signout_action.triggered.connect(self.sign_out)
        toolbar.addAction(signout_action)
    
        
    def create_visibility_info(self):
        group_box = QGroupBox("Feedback Visibility Information")
        group_box.setStyleSheet("""
            QGroupBox {
                font-size: 14px;
                font-weight: bold;
                margin-top: 10px;
                padding-top: 15px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Get management chain
        manager_chain = HierarchyValidator.get_manager_chain(self.username)
        
        if not manager_chain:
            layout.addWidget(QLabel("You are at the top level - feedback is visible to organization leadership"))
            group_box.setLayout(layout)
            return group_box
        
        # Get direct manager
        direct_manager = manager_chain[0]
        indirect_managers = manager_chain[1:]
        
        # Create HTML content with styling
        content = """
            <style>
                .direct { color: #2ecc71; font-weight: bold; }
                .indirect { color: #3498db; }
                .note { color: #e67e22; font-style: italic; }
                ul { margin-left: 20px; padding-left: 0; }
            </style>
        """
        
        content += "<p>Your feedback visibility:</p><ul>"
        
        # Direct manager section
        direct_reportees = sum(len(r) for r in HierarchyValidator.get_all_reportees(direct_manager))
        content += f"""
            <li><span class='direct'>Direct Manager ({direct_manager}):</span><br>
            - Can view detailed feedback<br>
            - Has {direct_reportees} reportees</li>
        """
        
        # Indirect managers section
        if indirect_managers:
            content += "<li><span class='indirect'>Indirect Managers:</span><ul>"
            for manager in indirect_managers:
                dir_r, indir_r = HierarchyValidator.get_all_reportees(manager)
                total_r = len(dir_r) + len(indir_r)
                content += f"""
                    <li>{manager}<br>
                    - Sees aggregated indirect feedback<br>
                    - Manages {total_r} employees total"""
                
                if total_r < 5:
                    content += "<br><span class='note'>Note: Despite small team size, feedback remains anonymous</span>"
                
                content += "</li>"
            content += "</ul></li>"
        
        content += "</ul>"
        
        if direct_reportees < 5:
            content += """
            <p class='note'>Note: When managers have fewer than 5 direct reportees, 
            feedback is still collected but displayed as indirect feedback 
            to their managers to preserve anonymity.</p>
            """
        
        label = QLabel(content)
        label.setWordWrap(True)
        label.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(label)
        
        group_box.setLayout(layout)
        return group_box

        
    def check_feedback_before_analysis(self):
        conn = sqlite3.connect('feedback.db')
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM feedback_responses WHERE manager = ?', (self.username,))
        response_count = cursor.fetchone()[0]
        conn.close()
        
        if response_count == 0:
            QMessageBox.information(
                self,
                "No Feedback Data",
                "No responses submitted yet.\nPlease try again later.",
                QMessageBox.StandardButton.Ok
            )
        else:
            self.show_analysis()

    def sign_out(self):
        # Clear user session data
        self.username = None
        QMessageBox.information(self, "Signed Out", "You have been successfully signed out")
        
        # Return to login window
        self.login_window = FeedbackLoginWindow()
        self.login_window.show()
        self.close()
    
    # def show_analysis(self):
    #     dialog = FeedbackAnalysisDialog(self.username, self.feedback_db)
    #     dialog.exec()
    def show_analysis(self):
        if not hasattr(self, 'private_key') or not self.private_key:
            QMessageBox.warning(self, "Decryption Error",
                "Private key not available for decryption")
            return
            
        dialog = FeedbackAnalysisDialog(self.username, self.feedback_db, self.private_key)
        dialog.exec()

    def update_approval_status(self):
        approved = self.feedback_db.get_user_status(self.username)
        status = "Approved" if approved else "Pending Approval - Feedback will be recorded but marked unapproved"
        self.approval_label.setText(f"Account Status: {status}")

    # In FeedbackMainWindow class
    def open_survey(self):
        manager_name = self.get_manager_name()
        if manager_name:
            self.survey_dialog = SurveyApp(
                current_user=self.username,
                manager_name=manager_name,
                feedback_db=self.feedback_db  # Pass database reference
            )
            self.survey_dialog.exec()
        else:
            QMessageBox.warning(self, "Warning", "Manager information not found")

    def get_manager_name(self):
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.name 
            FROM employees e
            JOIN employees m ON e.manager_id = m.id
            WHERE e.name = ?
        ''', (self.username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else None
    
class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name,feedback_db):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.feedback_db = feedback_db
        self.attendance_db = AttendanceDB()
        self.setWindowTitle(f"Feedback Survey Form - {current_user}")
        self.resize(800, 600)
        
        # Load questions from Excel
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            return
            
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Create feedback type buttons
        self.feedback_type_layout = QHBoxLayout()
        self.lm_feedback_btn = QPushButton("LM Feedback")
        self.general_feedback_btn = QPushButton("General Feedback")
        
        self.feedback_type_layout.addWidget(self.lm_feedback_btn)
        self.feedback_type_layout.addWidget(self.general_feedback_btn)
        
        # Create stacked widget
        self.stacked_widget = QStackedWidget()
        
        # Create pages
        self.create_lm_feedback_page()
        self.create_general_feedback_page()
        
        # Connect buttons
        self.lm_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.general_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        
        # Submit button
        self.submit_btn = QPushButton("Submit Feedback")
        self.submit_btn.clicked.connect(self.submit_feedback)
        
        main_layout.addLayout(self.feedback_type_layout)
        main_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(self.submit_btn)
        
        self.setLayout(main_layout)
    
    def create_lm_feedback_page(self):
        lm_page = QWidget()
        lm_layout = QVBoxLayout(lm_page)
        
        self.lm_tabs = QTabWidget()
        self.lm_responses = {}
        
        # Get all category columns dynamically
        categories = self.questions_df['Category'].unique().tolist()
        
        for category in categories:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            container = QWidget()
            layout = QVBoxLayout(container)
            
            category_questions = self.questions_df[self.questions_df['Category'] == category]
            
            for _, row in category_questions.iterrows():
                q_id = row['QuestionID']
                question_text = row['Question']
                
                # Get all available options dynamically
                options = []
                option_num = 1
                while f'Option{option_num}' in row:
                    opt = row[f'Option{option_num}']
                    if pd.notna(opt):
                        options.append(opt)
                        option_num += 1
                    else:
                        break
                        
                # Create question UI elements
                group_box = QGroupBox(question_text)
                group_layout = QVBoxLayout()
                
                option_group = QButtonGroup(self)
                self.lm_responses[q_id] = None
                
                for i, option in enumerate(options, start=1):
                    radio = QRadioButton(option)
                    radio.toggled.connect(
                        lambda state, qid=q_id, val=i: self.on_radio_toggled(state, qid, val)
                    )
                    group_layout.addWidget(radio)
                
                group_box.setLayout(group_layout)
                layout.addWidget(group_box)
            
            scroll.setWidget(container)
            self.lm_tabs.addTab(scroll, category)
        
        lm_layout.addWidget(self.lm_tabs)
        self.stacked_widget.addWidget(lm_page)
        
    def create_general_feedback_page(self):
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        
        self.general_feedback_input = QTextEdit()
        general_layout.addWidget(QLabel("General Feedback:"))
        general_layout.addWidget(self.general_feedback_input)
        
        self.stacked_widget.addWidget(general_page)

    def on_radio_toggled(self, state, q_id, value):
        if state:
            self.lm_responses[q_id] = value

    # def submit_feedback(self):
    #     # 1. Validate all questions are answered
    #     missing_questions = [
    #         qid for qid, response in self.lm_responses.items()
    #         if response is None
    #     ]
        
    #     if missing_questions:
    #         QMessageBox.warning(
    #             self, 
    #             "Incomplete Feedback",
    #             "Please answer all mandatory questions before submitting.",
    #             QMessageBox.StandardButton.Ok
    #         )
    #         return

    #     # 2. Check if already submitted this period
    #     if not self.attendance_db.mark_submission(self.current_user):
    #         QMessageBox.warning(
    #             self, 
    #             "Already Submitted",
    #             "You've already submitted feedback this period!\nYou can only submit once per month.",
    #             QMessageBox.StandardButton.Ok
    #         )
    #         return
        
    #     # 3. Get approval status
    #     approval_status = self.feedback_db.get_user_status(self.current_user)
    #     if approval_status is None:
    #         approval_status = False

    #     # 4. Get management chain
    #     manager_chain = HierarchyValidator.get_manager_chain(self.current_user)
    #     if not manager_chain:
    #         QMessageBox.critical(
    #             self,
    #             "Organization Error",
    #             "No management chain found for your account!\nPlease contact HR.",
    #             QMessageBox.StandardButton.Ok
    #         )
    #         return

    #     # 5. Determine reportee type (direct/indirect)
    #     direct_reportees, indirect_reportees = HierarchyValidator.get_all_reportees(self.manager_name)
    #     reportee_type = "direct" if self.current_user in direct_reportees else "indirect"

    #     # 6. Prepare feedback package
    #     feedback_data = {
    #         "responder": self.current_user,
    #         "reportee_type": reportee_type,
    #         "responses": self.lm_responses,
    #         "general_feedback": self.general_feedback_input.toPlainText(),
    #         "timestamp": datetime.now().isoformat(),
    #         "approval_status": approval_status
    #     }
        
    #     try:
    #         json_data = json.dumps(feedback_data, separators=(',', ':')).encode('utf-8')
    #     except Exception as e:
    #         QMessageBox.critical(
    #             self,
    #             "Data Error",
    #             f"Failed to prepare feedback data: {str(e)}",
    #             QMessageBox.StandardButton.Ok
    #         )
    #         return

    #     # 7. Encrypt for each manager in chain
    #     conn = sqlite3.connect('feedback.db')
    #     cursor = conn.cursor()
    #     successful_submissions = 0
        
    #     try:
    #         # Generate random AES key and IV for this submission
    #         aes_key = os.urandom(32)  # 256-bit key
    #         iv = os.urandom(16)       # 128-bit IV
            
    #         # Encrypt data with AES
    #         cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    #         encrypted_data = cipher.encrypt(pad(json_data, AES.block_size))

    #         for manager in manager_chain:
    #             try:
    #                 # Load manager's public key
    #                 public_key_path = f"{manager}_public.pem"
    #                 if not os.path.exists(public_key_path):
    #                     QMessageBox.warning(
    #                         self,
    #                         "Key Not Found",
    #                         f"Public key not found for {manager}.\nFeedback won't be sent to this manager.",
    #                         QMessageBox.StandardButton.Ok
    #                     )
    #                     continue
                    
    #                 with open(public_key_path, "rb") as f:
    #                     public_key = serialization.load_pem_public_key(f.read())
                    
    #                 # Encrypt the AES key with RSA
    #                 encrypted_key = public_key.encrypt(
    #                     aes_key,
    #                     padding.OAEP(
    #                         mgf=padding.MGF1(algorithm=hashes.SHA256()),
    #                         algorithm=hashes.SHA256(),
    #                         label=None
    #                     )
    #                 )
                    
    #                 # Combine IV (16) + encrypted key (256) + encrypted data
    #                 package = iv + encrypted_key + encrypted_data
                    
    #                 # Store in database
    #                 cursor.execute('''
    #                     INSERT INTO feedback_responses 
    #                     (manager, encrypted_data, approval_status)
    #                     VALUES (?, ?, ?)
    #                 ''', (manager, package, approval_status))
                    
    #                 successful_submissions += 1
                    
    #             except Exception as e:
    #                 QMessageBox.warning(
    #                     self,
    #                     "Encryption Error",
    #                     f"Failed to encrypt for {manager}:\n{str(e)}\nFeedback won't be sent to this manager.",
    #                     QMessageBox.StandardButton.Ok
    #                 )
    #                 continue
            
    #         # 8. Finalize submission
    #         if successful_submissions > 0:
    #             conn.commit()
    #             QMessageBox.information(
    #                 self,
    #                 "Success",
    #                 f"Feedback successfully submitted to {successful_submissions} manager(s)!",
    #                 QMessageBox.StandardButton.Ok
    #             )
    #             self.close()
    #         else:
    #             conn.rollback()
    #             QMessageBox.critical(
    #                 self,
    #                 "Submission Failed",
    #                 "Failed to submit feedback to any manager!",
    #                 QMessageBox.StandardButton.Ok
    #             )
                
    #     except Exception as e:
    #         conn.rollback()
    #         QMessageBox.critical(
    #             self,
    #             "System Error",
    #             f"Critical error during submission:\n{str(e)}",
    #             QMessageBox.StandardButton.Ok
    #         )
    #     finally:
    #         conn.close()


    def submit_feedback(self):
        # 1. Validate all questions are answered
        missing_questions = [
            qid for qid, response in self.lm_responses.items()
            if response is None
        ]
        
        if missing_questions:
            QMessageBox.warning(
                self, 
                "Incomplete Feedback",
                "Please answer all mandatory questions before submitting.",
                QMessageBox.StandardButton.Ok
            )
            return

        # 2. Check if already submitted this period
        if not self.attendance_db.mark_submission(self.current_user):
            QMessageBox.warning(
                self, 
                "Already Submitted",
                "You've already submitted feedback this period!\nYou can only submit once per month.",
                QMessageBox.StandardButton.Ok
            )
            return
        
        # 3. Get approval status
        approval_status = self.feedback_db.get_user_status(self.current_user)
        if approval_status is None:
            approval_status = False

        # Get the complete management chain including self
        full_chain = [self.current_user] + HierarchyValidator.get_manager_chain(self.current_user)
        
        # Prepare feedback package (without reportee_type yet)
        feedback_data = {
            "responder": self.current_user,
            "responses": self.lm_responses,
            "general_feedback": self.general_feedback_input.toPlainText(),
            "timestamp": datetime.now().isoformat(),
            "approval_status": approval_status
        }
        
        conn = sqlite3.connect('feedback.db')
        cursor = conn.cursor()
        successful_submissions = 0
        
        try:
            # Generate random AES key and IV for this submission
            aes_key = os.urandom(32)
            iv = os.urandom(16)
            cipher = AES.new(aes_key, AES.MODE_CBC, iv)
            encrypted_data = cipher.encrypt(pad(json.dumps(feedback_data, separators=(',', ':')).encode('utf-8'), AES.block_size))

            # Process each manager in the chain with proper reportee_type
            for i, manager in enumerate(full_chain[1:]):  # Skip the first element (self)
                try:
                    # Determine reportee_type for this specific manager
                    if i == 0:
                        # Immediate manager gets direct feedback
                        reportee_type = "direct"
                    else:
                        # Higher managers get indirect feedback
                        reportee_type = "indirect"
                    
                    # Add reportee_type to the feedback data
                    feedback_data["reportee_type"] = reportee_type
                    json_data = json.dumps(feedback_data, separators=(',', ':')).encode('utf-8')
                    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
                    encrypted_data = cipher.encrypt(pad(json_data, AES.block_size))

                    # Load manager's public key
                    public_key_path = f"{manager}_public.pem"
                    if not os.path.exists(public_key_path):
                        continue  # Skip if no key
                    
                    with open(public_key_path, "rb") as f:
                        public_key = serialization.load_pem_public_key(f.read())
                    
                    encrypted_key = public_key.encrypt(
                        aes_key,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    
                    package = iv + encrypted_key + encrypted_data
                    
                    cursor.execute('''
                        INSERT INTO feedback_responses 
                        (manager, encrypted_data, approval_status)
                        VALUES (?, ?, ?)
                    ''', (manager, package, approval_status))
                    
                    successful_submissions += 1
                    
                except Exception as e:
                    print(f"Skipping {manager} due to error: {str(e)}")
                    continue
            
            if successful_submissions > 0:
                conn.commit()
                QMessageBox.information(
                    self,
                    "Success",
                    f"Feedback submitted to {successful_submissions} manager(s)!",
                    QMessageBox.StandardButton.Ok
                )
                self.close()
            else:
                conn.rollback()
                QMessageBox.critical(
                    self,
                    "Error",
                    "Failed to submit to any manager!",
                    QMessageBox.StandardButton.Ok
                )
                
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(
                self,
                "Error",
                f"Submission failed: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
        finally:
            conn.close()

class FeedbackAnalysisDialog(QDialog):
    def __init__(self, username, feedback_db, private_key):
        super().__init__()
        self.username = username
        self.feedback_db = feedback_db
        self.private_key = private_key
        self.include_unapproved = False
        self.merged_data = pd.DataFrame()  # Initialize empty DataFrame
        self.responses_df = pd.DataFrame()
        self.general_feedback_df = pd.DataFrame()
        self.attendance_db = AttendanceDB()
        self.setWindowTitle(f"Feedback Analysis - {username}")
        self.resize(1200, 900)
        
        # Load questions
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions: {str(e)}")
            self.close()
        
        self.init_ui()
        self.load_data()

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Header
        header = QLabel(f"Analysis for: {self.username}")
        header.setStyleSheet("font-size: 18px; font-weight: bold; color: #2c3e50;")
        main_layout.addWidget(header)

        # Add include unapproved checkbox
        self.unapproved_check = QCheckBox("Include unapproved feedback?")
        self.unapproved_check.stateChanged.connect(self.toggle_unapproved)  # This is correct
        main_layout.addWidget(self.unapproved_check)
        
        # Add submission count label after header
        self.submission_count_label = QLabel()
        self.submission_count_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        main_layout.insertWidget(1, self.submission_count_label)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Analysis")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #2980b9; }
        """)
        refresh_btn.clicked.connect(self.load_data)
        main_layout.addWidget(refresh_btn)

        # Add submission count label
        self.submission_count_label = QLabel()
        self.submission_count_label.setStyleSheet("color: #27ae60; font-weight: bold;")
        main_layout.insertWidget(1, self.submission_count_label)


        # Tab widget
        self.tabs = QTabWidget()
        
        # Add tabs
        self.create_overall_tab()
        self.create_section_tab()
        self.create_question_tab()
        # Add General Feedback tab
        self.create_general_feedback_tab()
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)
    def create_general_feedback_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.general_feedback_list = QListWidget()
        self.general_feedback_list.setStyleSheet("""
            QListWidget::item {
                border-bottom: 1px solid #ddd;
                padding: 8px;
            }
        """)
        
        layout.addWidget(QLabel("General Feedback Comments:"))
        layout.addWidget(self.general_feedback_list)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "General Feedback")
        
    # In FeedbackAnalysisDialog class
    def toggle_unapproved(self, state):
        """Handle checkbox state change"""
        self.include_unapproved = state == 2
        print(f"Including unapproved: {self.include_unapproved}, State {state}")  # Debug
        self.load_data()

    # def load_data(self):
    #     try:
    #         conn = sqlite3.connect('feedback.db')
    #         query = '''
    #             SELECT encrypted_data 
    #             FROM feedback_responses
    #             WHERE manager = ?
    #             AND (approval_status = 1 OR ? = 1)
    #         '''
    #         params = (self.username, int(self.include_unapproved))
            
    #         decrypted_responses = []
            
    #         for row in conn.execute(query, params):
    #             package = row[0]
                
    #             try:
    #                 if not hasattr(self.parent(), 'private_key') or not self.parent().private_key:
    #                     raise ValueError("No private key available for decryption")
                    
    #                 # Extract components from package
    #                 iv = package[:16]
    #                 encrypted_key = package[16:16+256]  # RSA 2048-bit encrypted key
    #                 encrypted_data = package[16+256:]
                    
    #                 # Decrypt AES key with RSA
    #                 aes_key = self.parent().private_key.decrypt(
    #                     encrypted_key,
    #                     padding.OAEP(
    #                         mgf=padding.MGF1(algorithm=hashes.SHA256()),
    #                         algorithm=hashes.SHA256(),
    #                         label=None
    #                     )
    #                 )
                    
    #                 # Decrypt data with AES
    #                 cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    #                 decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    #                 response_data = json.loads(decrypted.decode('utf-8'))
    #                 decrypted_responses.append(response_data)
                    
    #             except Exception as e:
    #                 print(f"Decryption failed: {str(e)}")
    #                 continue
            
        
    #         # Process decrypted data
    #         if decrypted_responses:
    #             response_rows = []
    #             feedback_rows = []
                
    #             for data in decrypted_responses:
    #                 # Process question responses
    #                 for qid, resp in data.get('responses', {}).items():
    #                     response_rows.append({
    #                         'question_id': qid,
    #                         'response': resp,
    #                         'timestamp': data['timestamp']
    #                     })
                    
    #                 # Process general feedback
    #                 if data.get('general_feedback'):
    #                     feedback_rows.append({
    #                         'general_feedback': data['general_feedback'],
    #                         'timestamp': data['timestamp']
    #                     })
                
    #             self.responses_df = pd.DataFrame(response_rows)
    #             self.general_feedback_df = pd.DataFrame(feedback_rows)
                
    #             # Merge with questions
    #             if not self.responses_df.empty:
    #                 self.merged_data = pd.merge(
    #                     self.responses_df,
    #                     self.questions_df,
    #                     left_on='question_id',
    #                     right_on='QuestionID',
    #                     how='left'
    #                 )
    #                 # Convert to percentage
    #                 self.merged_data['response_pct'] = (
    #                     (self.merged_data['response'] - 1) / 3 * 100
    #                 )
            
    #         # Update UI
    #         self.update_submission_count()
    #         self.update_analyses()
    #         self.update_general_feedback_list()
            
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", 
    #             f"Data loading failed: {str(e)}")
    #     finally:
    #         conn.close()

    # def load_data(self):
    #     try:
    #         conn = sqlite3.connect('feedback.db')
    #         query = '''
    #             SELECT encrypted_data 
    #             FROM feedback_responses
    #             WHERE manager = ?
    #             AND (approval_status = 1 OR ? = 1)
    #         '''
    #         params = (self.username, int(self.include_unapproved))
            
    #         decrypted_responses = []
            
    #         for row in conn.execute(query, params):
    #             package = row[0]
                
    #             try:
    #                 if not self.private_key:
    #                     raise ValueError("Private key not loaded")
                    
    #                 # Extract components from package
    #                 iv = package[:16]
    #                 encrypted_key = package[16:16+256]
    #                 encrypted_data = package[16+256:]
                    
    #                 # Decrypt AES key
    #                 aes_key = self.private_key.decrypt(
    #                     encrypted_key,
    #                     padding.OAEP(
    #                         mgf=padding.MGF1(algorithm=hashes.SHA256()),
    #                         algorithm=hashes.SHA256(),
    #                         label=None
    #                     )
    #                 )
                    
    #                 # Decrypt data
    #                 cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    #                 decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    #                 response_data = json.loads(decrypted.decode('utf-8'))
    #                 decrypted_responses.append(response_data)
                    
    #             except Exception as e:
    #                 print(f"Decryption failed for a record: {str(e)}")
    #                 continue
                 
    #         # Process decrypted data
    #         if decrypted_responses:
    #             response_rows = []
    #             feedback_rows = []
                
    #             for data in decrypted_responses:
    #                 # Process question responses
    #                 for qid, resp in data.get('responses', {}).items():
    #                     response_rows.append({
    #                         'question_id': qid,
    #                         'response': resp,
    #                         'timestamp': data['timestamp']
    #                     })
                    
    #                 # Process general feedback
    #                 if data.get('general_feedback'):
    #                     feedback_rows.append({
    #                         'general_feedback': data['general_feedback'],
    #                         'timestamp': data['timestamp']
    #                     })
                
    #             self.responses_df = pd.DataFrame(response_rows)
    #             self.general_feedback_df = pd.DataFrame(feedback_rows)
                
    #             # Merge with questions
    #             if not self.responses_df.empty:
    #                 self.merged_data = pd.merge(
    #                     self.responses_df,
    #                     self.questions_df,
    #                     left_on='question_id',
    #                     right_on='QuestionID',
    #                     how='left'
    #                 )
    #                 # Convert to percentage
    #                 self.merged_data['response_pct'] = (
    #                     (self.merged_data['response'] - 1) / 3 * 100
    #                 )
            
    #         # Update UI
    #         self.update_submission_count()
    #         self.update_analyses()
    #         self.update_general_feedback_list()
            
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", 
    #             f"Data loading failed: {str(e)}")
    #     finally:
    #         conn.close()

    def load_data(self):
        try:
            conn = sqlite3.connect('feedback.db')
            query = '''
                SELECT encrypted_data 
                FROM feedback_responses
                WHERE manager = ?
                AND (approval_status = 1 OR ? = 1)
            '''
            params = (self.username, int(self.include_unapproved))
            
            response_rows = []
            feedback_rows = []
            
            for row in conn.execute(query, params):
                package = row[0]
                
                try:
                    if not self.private_key:
                        raise ValueError("Private key not loaded")
                    
                    # Extract and decrypt components
                    iv = package[:16]
                    encrypted_key = package[16:16+256]
                    encrypted_data = package[16+256:]
                    
                    aes_key = self.private_key.decrypt(
                        encrypted_key,
                        padding.OAEP(
                            mgf=padding.MGF1(algorithm=hashes.SHA256()),
                            algorithm=hashes.SHA256(),
                            label=None
                        )
                    )
                    
                    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
                    decrypted = unpad(cipher.decrypt(encrypted_data), AES.block_size)
                    response_data = json.loads(decrypted.decode('utf-8'))
                    
                    # Process responses
                    for q_id, response in response_data.get('responses', {}).items():
                        response_rows.append({
                            'question_id': q_id,
                            'response': response,
                            'reportee_type': response_data.get('reportee_type', 'unknown'),
                            'timestamp': response_data['timestamp']
                        })
                    
                    # Process general feedback
                    if response_data.get('general_feedback'):
                        feedback_rows.append({
                            'feedback': response_data['general_feedback'],
                            'reportee_type': response_data.get('reportee_type', 'unknown'),
                            'timestamp': response_data['timestamp']
                        })
                    
                except Exception as e:
                    print(f"Skipping record due to error: {str(e)}")
                    continue
            
            # Create DataFrames
            self.responses_df = pd.DataFrame(response_rows)
            self.general_feedback_df = pd.DataFrame(feedback_rows)
            
            # Merge with questions if responses exist
            if not self.responses_df.empty:
                self.merged_data = pd.merge(
                    self.responses_df,
                    self.questions_df,
                    left_on='question_id',
                    right_on='QuestionID',
                    how='left'
                )
                # Convert to percentage
                self.merged_data['response_pct'] = (
                    (self.merged_data['response'] - 1) / 3 * 100
                )
            
            # Update UI
            self.update_submission_count()
            self.update_analyses()
            self.update_general_feedback_list()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", 
                f"Data loading failed: {str(e)}")
        finally:
            conn.close()

    def convert_to_percentage(self, series):
        """Convert 1-4 scale to 0-100% scale"""
        return ((series.mean() - 1) / 3 * 100) if not series.empty else 0

    def create_overall_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.overall_canvas = FigureCanvas(Figure(figsize=(10, 6)))
        layout.addWidget(self.overall_canvas)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Overall Analysis")

    # def update_submission_count(self):
    #     """Update the submission count label"""
    #     conn = sqlite3.connect('attendance.db')
    #     try:
    #         # Get all reportees
    #         direct, indirect = HierarchyValidator.get_all_reportees(self.username)
            
    #         # Get submission counts
    #         submitted_direct = 0
    #         submitted_indirect = 0
            
    #         if direct:
    #             placeholders = ','.join(['?']*len(direct))
    #             cursor = conn.execute(f'''
    #                 SELECT COUNT(DISTINCT username) 
    #                 FROM submissions 
    #                 WHERE username IN ({placeholders})
    #             ''', direct)
    #             submitted_direct = cursor.fetchone()[0] or 0
                
    #         if indirect:
    #             placeholders = ','.join(['?']*len(indirect))
    #             cursor = conn.execute(f'''
    #                 SELECT COUNT(DISTINCT username) 
    #                 FROM submissions 
    #                 WHERE username IN ({placeholders})
    #             ''', indirect)
    #             submitted_indirect = cursor.fetchone()[0] or 0
                
    #         self.submission_count_label.setText(
    #             f"Direct Reportees Submitted: {submitted_direct}/{len(direct)}   "
    #             f"Indirect Reportees Submitted: {submitted_indirect}/{len(indirect)}"
    #         )
    #     finally:
    #         conn.close()

    def update_submission_count(self):
        try:
            conn = sqlite3.connect('attendance.db')
            
            # Get all reportees
            direct, indirect = HierarchyValidator.get_all_reportees(self.username)
            
            # Get submission counts
            submitted_direct = 0
            submitted_indirect = 0
            
            if direct:
                placeholders = ','.join(['?']*len(direct))
                cursor = conn.execute(f'''
                    SELECT COUNT(DISTINCT username) 
                    FROM submissions 
                    WHERE username IN ({placeholders})
                ''', direct)
                submitted_direct = cursor.fetchone()[0] or 0
                
            if indirect:
                placeholders = ','.join(['?']*len(indirect))
                cursor = conn.execute(f'''
                    SELECT COUNT(DISTINCT username) 
                    FROM submissions 
                    WHERE username IN ({placeholders})
                ''', indirect)
                submitted_indirect = cursor.fetchone()[0] or 0
                
            self.submission_count_label.setText(
                f"Direct Reportees Submitted: {submitted_direct}/{len(direct)}\n"
                f"Indirect Reportees Submitted: {submitted_indirect}/{len(indirect)}"
            )
        finally:
            conn.close()

    # def update_general_feedback_list(self):
    #     """Update the general feedback list widget"""
    #     self.general_feedback_list.clear()
    #     if not self.general_feedback_df.empty:
    #         for _, row in self.general_feedback_df.iterrows():
    #             item = QListWidgetItem()
    #             item.setText(f"{row['timestamp']}\n{row['general_feedback']}")
    #             item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
    #             self.general_feedback_list.addItem(item)

    def update_general_feedback_list(self):
        self.general_feedback_list.clear()
        if not self.general_feedback_df.empty:
            for _, row in self.general_feedback_df.iterrows():
                item = QListWidgetItem()
                item.setText(
                    f"{row['timestamp']} ({row['reportee_type']})\n"
                    f"{row['feedback']}"
                )
                item.setData(Qt.UserRole, row['reportee_type'])
                
                # Color code by reportee type
                if row['reportee_type'] == 'direct':
                    item.setForeground(QColor('#3498db'))  # Blue
                else:
                    item.setForeground(QColor('#2ecc71'))  # Green
                    
                self.general_feedback_list.addItem(item)

    # def update_overall_analysis(self):
    #     fig = self.overall_canvas.figure
    #     fig.clear()
        
    #     # Get data
    #     direct_data = self.merged_data[self.merged_data['reportee_type'] == 'direct']
    #     indirect_data = self.merged_data[self.merged_data['reportee_type'] == 'indirect']
        
    #     has_direct = not direct_data.empty
    #     has_indirect = not indirect_data.empty
        
    #     if not has_direct and not has_indirect:
    #         ax = fig.add_subplot(111)
    #         ax.text(0.5, 0.5, 'No feedback data available', 
    #             ha='center', va='center', fontsize=12)
    #         self.overall_canvas.draw()
    #         return

    #     # Calculate response counts for pie chart
    #     direct_count = len(direct_data)
    #     indirect_count = len(indirect_data)
    #     total_responses = direct_count + indirect_count

    #     if has_direct and has_indirect:
    #         # Pie chart for response distribution
    #         ax = fig.add_subplot(111)
    #         labels = ['Direct Feedback', 'Indirect Feedback']
    #         sizes = [direct_count, indirect_count]
    #         colors = ['#3498db', '#2ecc71']
    #         explode = (0.1, 0)  # emphasize direct feedback

    #         wedges, texts, autotexts = ax.pie(
    #         sizes, 
    #         explode=explode, 
    #         labels=labels, 
    #         colors=colors,
    #         autopct=lambda p: f'{p:.1f}%' if p >= 25 else '',
    #         startangle=140,
    #         wedgeprops={'edgecolor': 'white', 'linewidth': 2},
    #         textprops={'fontsize': 10}
    #         )

    #         ax.set_title('Feedback Response Distribution', fontsize=14, pad=20)
    #         ax.axis('equal')  # Equal aspect ratio ensures pie is drawn as circle
            

    #     else:
    #         # Bar chart for single feedback type
    #         ax = fig.add_subplot(111)
    #         feedback_type = 'Direct' if has_direct else 'Indirect'
    #         avg_score = self.convert_to_percentage(
    #             direct_data['response'] if has_direct else indirect_data['response']
    #         )

    #         bars = ax.bar([feedback_type], [avg_score], 
    #                     color='#3498db', width=0.6)
    #         ax.set_ylim(0, 100)
    #         ax.set_ylabel('Average Score (%)')
    #         ax.set_title(f'{feedback_type} Feedback Score', fontsize=14)
            
    #         # Add value label
    #         for bar in bars:
    #             height = bar.get_height()
    #             ax.text(bar.get_x() + bar.get_width()/2., height,
    #                     f'{height:.1f}%', ha='center', va='bottom', fontsize=12)

    #     # self.overall_canvas.tight_layout()
    #     fig.tight_layout()

    #     self.overall_canvas.draw()

    def update_overall_analysis(self):
        fig = self.overall_canvas.figure
        fig.clear()
        
        # Get data
        direct_data = self.merged_data[self.merged_data['reportee_type'] == 'direct']
        indirect_data = self.merged_data[self.merged_data['reportee_type'] == 'indirect']
        
        # Calculate scores
        direct_avg = direct_data['response_pct'].mean() if not direct_data.empty else 0
        indirect_avg = indirect_data['response_pct'].mean() if not indirect_data.empty else 0
        overall_avg = self.merged_data['response_pct'].mean() if not self.merged_data.empty else 0

        has_direct = not direct_data.empty
        has_indirect = not indirect_data.empty
        
        if not has_direct and not has_indirect:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No feedback data available', 
                ha='center', va='center', fontsize=12)
            self.overall_canvas.draw()
            return

        # Create labels with score percentages
        labels = []
        sizes = []
        score_labels = []
        
        if has_direct:
            labels.append('Direct Feedback')
            sizes.append(len(direct_data))
            score_labels.append(f'Score: {direct_avg:.1f}%')
            
        if has_indirect:
            labels.append('Indirect Feedback')
            sizes.append(len(indirect_data))
            score_labels.append(f'Score: {indirect_avg:.1f}%')

        # Create combined labels
        combined_labels = [f"{label}\n{score}" for label, score in zip(labels, score_labels)]

        # Create pie chart
        ax = fig.add_subplot(111)
        wedges, texts, autotexts = ax.pie(
            sizes,
            labels=combined_labels,
            autopct=lambda p: f'{p:.1f}%',
            startangle=140,
            colors=['#3498db', '#2ecc71'],
            wedgeprops={'edgecolor': 'white', 'linewidth': 2},
            textprops={'fontsize': 10}
        )

        # Adjust label positions
        plt.setp(texts, path_effects=[patheffects.withStroke(linewidth=3, foreground="white")])
        
        # Add overall score title
        ax.set_title(f'Overall Score: {overall_avg:.1f}%', 
                    fontsize=14, pad=20, fontweight='bold')
        
        self.overall_canvas.draw()

    def create_section_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Section selection
        self.section_combo = QComboBox()
        self.section_combo.addItems(self.questions_df['Category'].unique().tolist())
        self.section_combo.currentTextChanged.connect(self.update_section_analysis)
        
        # Info label
        info_label = QLabel("Select a category to view detailed breakdown")
        info_label.setStyleSheet("color: #7f8c8d; font-style: italic;")
        
        # Canvas setup
        self.section_canvas = FigureCanvas(Figure(figsize=(10, 6)))
        
        layout.addWidget(self.section_combo)
        layout.addWidget(info_label)
        layout.addWidget(self.section_canvas)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Category Analysis")

    def update_section_analysis(self, category):
        fig = self.section_canvas.figure
        fig.clear()
        ax = fig.add_subplot(111)
        
        # Filter data
        section_data = self.merged_data[self.merged_data['Category'] == category]
        
        if section_data.empty:
            ax.text(0.5, 0.5, 'No data available\nfor this category', 
                   ha='center', va='center', fontsize=12)
            self.section_canvas.draw()
            return
        
        # Calculate percentages
        direct_pct = self.convert_to_percentage(
            section_data[section_data['reportee_type'] == 'direct']['response']
        )
        indirect_pct = self.convert_to_percentage(
            section_data[section_data['reportee_type'] == 'indirect']['response']
        )
        
        # Create bar plot
        categories = ['Direct Feedback', 'Indirect Feedback']
        values = [direct_pct, indirect_pct]
        colors = ['#3498db', '#2ecc71']
        
        bars = ax.bar(categories, values, color=colors)
        ax.set_ylim(0, 100)
        ax.set_ylabel('Average Score (%)')
        ax.set_title(f'{category} Analysis', fontsize=14, fontweight='bold')
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.1f}%', ha='center', va='bottom',
                    fontsize=12, color='#2c3e50')
        
        # Style adjustments
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        self.section_canvas.draw()

    def create_question_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Category selection
        self.question_category_combo = QComboBox()
        self.question_category_combo.addItems(self.questions_df['Category'].unique().tolist())
        self.question_category_combo.currentTextChanged.connect(self.update_question_list)
        
        # Question selection
        self.question_combo = QComboBox()
        self.question_combo.currentTextChanged.connect(self.update_question_analysis)
        
        # Canvas setup
        self.question_canvas = FigureCanvas(Figure(figsize=(10, 6)))
        
        # Layout organization
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Category:"))
        selection_layout.addWidget(self.question_category_combo)
        selection_layout.addWidget(QLabel("Question:"))
        selection_layout.addWidget(self.question_combo)
        selection_layout.addStretch()
        
        layout.addLayout(selection_layout)
        layout.addWidget(self.question_canvas)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Question Analysis")
        
        self.update_question_list(self.question_category_combo.currentText())

    def update_question_list(self, category):
        self.question_combo.clear()
        questions = self.questions_df[self.questions_df['Category'] == category]
        for _, row in questions.iterrows():
            self.question_combo.addItem(row['Question'], row['QuestionID'])

    def update_question_analysis(self, question_text):
        fig = self.question_canvas.figure
        fig.clear()
        
        if not question_text or self.merged_data.empty:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available', 
                ha='center', va='center', fontsize=12)
            self.question_canvas.draw()
            return
            
        question_id = self.question_combo.currentData()
        question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
        
        if question_data.empty:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No data available\nfor this question', 
                ha='center', va='center', fontsize=12)
            self.question_canvas.draw()
            return
        
        try:
            # Split data into direct and indirect
            direct_data = question_data[question_data['reportee_type'] == 'direct']
            indirect_data = question_data[question_data['reportee_type'] == 'indirect']
            
            # Determine how many subplots we need
            has_direct = not direct_data.empty
            has_indirect = not indirect_data.empty
            
            if not has_direct and not has_indirect:
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, 'No data available', 
                    ha='center', va='center', fontsize=12)
                self.question_canvas.draw()
                return
                
            # Create subplots based on data availability
            if has_direct and has_indirect:
                ax1 = fig.add_subplot(121)
                ax2 = fig.add_subplot(122)
                axes = [(ax1, direct_data, 'Direct Responses'), 
                    (ax2, indirect_data, 'Indirect Responses')]
            else:
                ax = fig.add_subplot(111)
                data = direct_data if has_direct else indirect_data
                type_label = 'Direct' if has_direct else 'Indirect'
                axes = [(ax, data, f'{type_label} Responses')]

            def plot_pie(ax, data, title):
                if data.empty:
                    ax.axis('off')
                    return

                # Get actual question options from Excel data
                question_id = self.question_combo.currentData()
                question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
                
                # Get all available options dynamically
                options = []
                option_num = 1
                while f'Option{option_num}' in question_row:
                    opt = question_row[f'Option{option_num}']
                    if pd.notna(opt):
                        options.append(opt)
                        option_num += 1
                    else:
                        break
                        
                # Get response counts for available options
                response_counts = data['response'].astype(int).value_counts().sort_index()
                response_counts = response_counts.reindex(range(1, len(options)+1), fill_value=0)
                total = response_counts.sum()
                
                if total == 0:
                    ax.axis('off')
                    return
                    
                percentages = (response_counts / total) * 100
                
                # Create labels list with empty strings for <25%
                labels = [
                    option if pct >= 25 else '' 
                    for option, pct in zip(options, percentages)
                ]
                
                wedges, texts, autotexts = ax.pie(
                    percentages,
                    labels=labels,  # Use filtered labels
                    autopct=lambda p: f'{p:.1f}%' if p >= 25 else '',
                    startangle=90,
                    colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
                    wedgeprops={'width': 0.4, 'edgecolor': 'white'},
                    textprops={'fontsize': 8, 'color': 'white'}
                )
                
                # Force hide labels and percentages for <25%
                for i, pct in enumerate(percentages):
                    if pct < 25:
                        texts[i].set_visible(False)
                        autotexts[i].set_visible(False)
                
                ax.set_title(title, fontsize=10, pad=12)
                
                # Create compact legend for all options
                legend = ax.legend(
                    wedges,
                    options,
                    title="Response Options",
                    loc="upper center",
                    bbox_to_anchor=(0.5, -0.15),
                    ncol=2,
                    fontsize=8,
                    title_fontsize=9
                )
                    
            # Plot each chart
            for ax, data, title in axes:
                plot_pie(ax, data, title)
                
            # Adjust layout
            fig.tight_layout()
            self.question_canvas.draw()
            
        except Exception as e:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'Error displaying data\nPlease check input', 
                ha='center', va='center', fontsize=12, color='red')
            self.question_canvas.draw()

    def update_analyses(self):
        """Update all analysis views"""
        self.update_overall_analysis()
        current_section = self.section_combo.currentText()
        if current_section:
            self.update_section_analysis(current_section)
        current_question = self.question_combo.currentText()
        if current_question:
            self.update_question_analysis(current_question)

class AttendanceDB:
    def __init__(self):
        self.conn = sqlite3.connect('attendance.db')
        self.create_table()
        
    def create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                username TEXT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
        
    def mark_submission(self, username):
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                INSERT INTO submissions (username) VALUES (?)
            ''', (username,))
            self.conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already submitted
        
    def get_submission_count(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM submissions')
        return cursor.fetchone()[0]

if __name__ == '__main__':
    app = QApplication([])
    window = FeedbackLoginWindow()
    window.show()
    app.exec()
