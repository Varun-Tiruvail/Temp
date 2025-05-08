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
import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                manager TEXT NOT NULL,
                reportee_type TEXT NOT NULL,
                question_id TEXT,
                response INTEGER,
                general_feedback TEXT,
                approval_status BOOLEAN NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
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

        # Add Survey Button
        feedback_btn = QPushButton('Give Feedback')
        feedback_btn.clicked.connect(self.open_survey)
        layout.addWidget(feedback_btn)

        # Feedback Input
        # self.feedback_input = QTextEdit()
        # submit_btn = QPushButton('Submit Feedback')
        
        # Previous Feedback
        self.feedback_list = QListWidget()
        
        # Approval status indicator
        self.approval_label = QLabel()
        self.update_approval_status()
        layout.addWidget(self.approval_label)
        analysis_btn = QPushButton('View Analysis')
        analysis_btn.clicked.connect(self.show_analysis)
        layout.addWidget(analysis_btn)
    
    def show_analysis(self):
        dialog = FeedbackAnalysisDialog(self.username, self.feedback_db)
        dialog.exec()

    def update_approval_status(self):
        approved = self.feedback_db.get_user_status(self.username)
        status = "Approved" if approved else "Pending Approval - Feedback will be recorded but marked unapproved"
        self.approval_label.setText(f"Account Status: {status}")

    # def open_survey(self):
    #     # Get manager name from hierarchy
    #     manager_name = self.get_manager_name()
    #     if manager_name:
    #         self.survey_dialog = SurveyApp(self.username, manager_name)
    #         self.survey_dialog.exec()
    #     else:
    #         QMessageBox.warning(self, "Warning", "Manager information not found")

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
                
                group_box = QGroupBox(question_text)
                group_layout = QVBoxLayout()
                
                option_group = QButtonGroup(self)
                self.lm_responses[q_id] = None
                
                options = [row['Option1'], row['Option2'], row['Option3'], row['Option4']]
                
                for i, option in enumerate(options, start=1):
                    radio = QRadioButton(option)
                    radio.toggled.connect(lambda state, qid=q_id, val=i: self.on_radio_toggled(state, qid, val))
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
    
    def submit_feedback(self):

        # Check if already submitted
        if not self.attendance_db.mark_submission(self.current_user):
            QMessageBox.warning(self, "Error", "You've already submitted feedback! \n You can only submit once per month.")
            return
        
        # # Get approval status
        approval_status = self.feedback_db.get_user_status(self.current_user)
        # approval_status = self.parent().feedback_db.get_user_status(self.current_user)
        if approval_status is None:
            approval_status = False

        # Get management chain
        manager_chain = HierarchyValidator.get_manager_chain(self.current_user)
        if not manager_chain:
            QMessageBox.warning(self, "Error", "No management chain found!")
            return

        conn = sqlite3.connect('feedback.db')
        cursor = conn.cursor()
        

        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager TEXT NOT NULL,
                    reportee_type TEXT NOT NULL,
                    question_id TEXT,
                    response INTEGER,
                    general_feedback TEXT,
                    approval_status BOOLEAN NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Modified insertion logic for clarity
            for i, manager in enumerate(manager_chain):
                reportee_type = 'direct' if i == 0 else 'indirect'
                
                # Insert question responses
                for qid, response in self.lm_responses.items():
                    if response is not None:
                        cursor.execute('''
                            INSERT INTO feedback_responses 
                            (manager, reportee_type, question_id, response, approval_status)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (manager, reportee_type, qid, response, approval_status))

                # Insert general feedback
                general_feedback = self.general_feedback_input.toPlainText()
                if general_feedback:
                    cursor.execute('''
                        INSERT INTO feedback_responses 
                        (manager, reportee_type, general_feedback, approval_status)
                        VALUES (?, ?, ?, ?)
                    ''', (manager, reportee_type, general_feedback, approval_status))

            conn.commit()
            QMessageBox.information(self, "Success", "Feedback submitted to all relevant managers!")
            self.close()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to submit feedback: {str(e)}")
        finally:
            conn.close()

class FeedbackAnalysisDialog(QDialog):
    def __init__(self, username, feedback_db):
        super().__init__()
        self.username = username
        self.feedback_db = feedback_db
        self.include_unapproved = False
        self.merged_data = pd.DataFrame()  # Initialize empty DataFrame
        self.responses_df = pd.DataFrame()
        self.general_feedback_df = pd.DataFrame()
        self.attendance_db = AttendanceDB()
        self.setWindowTitle(f"Feedback Analysis - {username}")
        self.resize(1200, 900)
        # self.unapproved_check = QCheckBox("Include unapproved feedback?")
        # self.unapproved_check.stateChanged.connect(self.toggle_unapproved)
        
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
        
        main_layout.addWidget(self.tabs)
        self.setLayout(main_layout)

    # def toggle_unapproved(self, state):
    #     """Handle checkbox state change"""
    #     self.include_unapproved = state == Qt.Checked
    #     self.load_data()

    # def load_data(self):
    #     try:
    #         conn = sqlite3.connect('feedback.db')
            
    #         # Modified queries to filter by current user and approval status
    #         responses_query = """
    #             SELECT reportee_type, question_id, response, approval_status
    #             FROM feedback_responses
    #             WHERE manager = ? 
    #             AND (approval_status = 1 OR ?)
    #             AND response IS NOT NULL
    #         """
    #         self.responses_df = pd.read_sql_query(
    #             responses_query, conn, 
    #             params=(self.username, int(self.include_unapproved))
    #         )

    #         general_query = """
    #             SELECT general_feedback
    #             FROM feedback_responses
    #             WHERE manager = ? 
    #             AND (approval_status = 1 OR ?)
    #             AND general_feedback IS NOT NULL
    #         """
    #         self.general_feedback_df = pd.read_sql_query(
    #             general_query, conn,
    #             params=(self.username, int(self.include_unapproved))
    #         )
            
    #         # Convert responses to percentages
    #         if not self.responses_df.empty:
    #             self.responses_df['response'] = pd.to_numeric(self.responses_df['response'], errors='coerce')
    #             self.responses_df = self.responses_df.dropna(subset=['response'])
    #             self.responses_df['response_pct'] = ((self.responses_df['response'] - 1) / 3 * 100)
                
    #             # Merge with questions
    #             self.merged_data = pd.merge(
    #                 self.responses_df,
    #                 self.questions_df,
    #                 left_on='question_id',
    #                 right_on='QuestionID',
    #                 how='left'
    #             )
                
    #         # # Load general feedback
    #         # self.general_feedback_df = pd.read_sql_query("""
    #         #     SELECT manager, general_feedback
    #         #     FROM feedback_responses
    #         #     WHERE general_feedback IS NOT NULL AND approval_status = 1
    #         # """, conn)
            
    #         self.update_analyses()
            
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")
    #     finally:
    #         if 'conn' in locals():
    #             conn.close()

    def load_data(self):
        try:
            # Update submission count display
            count = self.attendance_db.get_submission_count()
            self.submission_count_label.setText(f"Total Users Submitted: {count}")
            conn = sqlite3.connect('feedback.db')
            
            # Clear previous data
            self.responses_df = pd.DataFrame()
            self.general_feedback_df = pd.DataFrame()
            self.merged_data = pd.DataFrame()

            # 1. Load responses with proper approval filtering
            responses_query = """
                SELECT reportee_type, question_id, response 
                FROM feedback_responses
                WHERE manager = ? 
                AND (approval_status = 1 OR ?)
            """
            self.responses_df = pd.read_sql_query(
                responses_query, conn, 
                params=(self.username, int(self.include_unapproved)))
            
            # Debug print
            print(f"Loaded {len(self.responses_df)} responses (unapproved: {self.include_unapproved})")

            # 2. Load general feedback
            general_query = """
                SELECT general_feedback
                FROM feedback_responses
                WHERE manager = ? 
                AND (approval_status = 1 OR ?)
                AND general_feedback IS NOT NULL
            """
            self.general_feedback_df = pd.read_sql_query(
                general_query, conn,
                params=(self.username, int(self.include_unapproved)))

            # 3. Process responses
            if not self.responses_df.empty:
                # Convert responses to numeric
                self.responses_df['response'] = pd.to_numeric(
                    self.responses_df['response'], 
                    errors='coerce'
                )
                # Remove invalid responses
                self.responses_df = self.responses_df.dropna(subset=['response'])
                # Convert to percentage
                self.responses_df['response_pct'] = (
                    (self.responses_df['response'] - 1) / 3 * 100
                )
                # Merge with questions
                self.merged_data = pd.merge(
                    self.responses_df,
                    self.questions_df,
                    left_on='question_id',
                    right_on='QuestionID',
                    how='left'
                )
                
            # Force UI refresh
            self.update_analyses()
            self.repaint()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")
        finally:
            if 'conn' in locals():
                conn.close()

    def toggle_unapproved(self, state):
        """Handle checkbox state change"""
        if state>0:
            self.include_unapproved = 1
        else:
            self.include_unapproved = 0
        # print(f"Unapproved filtering: {self.include_unapproved}")  # Debug
        print(f"Checkbox state: {state} → include_unapproved: {self.include_unapproved}")
        self.load_data()
        self.update_analyses()

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

    # def update_overall_analysis(self):
    #     fig = self.overall_canvas.figure
    #     fig.clear()
    #     ax = fig.add_subplot(111)
        
    #     # Calculate percentages
    #     direct_avg = self.convert_to_percentage(
    #         self.merged_data[self.merged_data['reportee_type'] == 'direct']['response']
    #     )
    #     indirect_avg = self.convert_to_percentage(
    #         self.merged_data[self.merged_data['reportee_type'] == 'indirect']['response']
    #     )
        
    #     # Plotting
    #     categories = ['Direct Feedback', 'Indirect Feedback']
    #     values = [direct_avg, indirect_avg]
        
    #     bars = ax.bar(categories, values, color=['#3498db', '#2ecc71'])
    #     ax.set_ylim(0, 100)
    #     ax.set_ylabel('Score (%)')
    #     ax.set_title('Overall Feedback Scores')
        
    #     # Add value labels
    #     for bar in bars:
    #         height = bar.get_height()
    #         ax.text(bar.get_x() + bar.get_width()/2., height,
    #                 f'{height:.1f}%', ha='center', va='bottom')
        
    #     self.overall_canvas.draw()

    def update_overall_analysis(self):
        fig = self.overall_canvas.figure
        fig.clear()
        
        # Get data
        direct_data = self.merged_data[self.merged_data['reportee_type'] == 'direct']
        indirect_data = self.merged_data[self.merged_data['reportee_type'] == 'indirect']
        
        has_direct = not direct_data.empty
        has_indirect = not indirect_data.empty
        
        if not has_direct and not has_indirect:
            ax = fig.add_subplot(111)
            ax.text(0.5, 0.5, 'No feedback data available', 
                ha='center', va='center', fontsize=12)
            self.overall_canvas.draw()
            return

        # Calculate response counts for pie chart
        direct_count = len(direct_data)
        indirect_count = len(indirect_data)
        total_responses = direct_count + indirect_count

        if has_direct and has_indirect:
            # Pie chart for response distribution
            ax = fig.add_subplot(111)
            labels = ['Direct Feedback', 'Indirect Feedback']
            sizes = [direct_count, indirect_count]
            colors = ['#3498db', '#2ecc71']
            explode = (0.1, 0)  # emphasize direct feedback

            # wedges, texts, autotexts = ax.pie(
            #     sizes, 
            #     explode=explode, 
            #     labels=labels, 
            #     colors=colors,
            #     autopct=lambda p: f'{p:.1f}%\n({int(p*total_responses/100)})',
            #     startangle=140,
            #     wedgeprops={'edgecolor': 'white', 'linewidth': 2},
            #     textprops={'fontsize': 12}
            # )
            wedges, texts, autotexts = ax.pie(
            sizes, 
            explode=explode, 
            labels=labels, 
            colors=colors,
            autopct=lambda p: f'{p:.1f}%' if p >= 25 else '',
            startangle=140,
            wedgeprops={'edgecolor': 'white', 'linewidth': 2},
            textprops={'fontsize': 10}
            )

            ax.set_title('Feedback Response Distribution', fontsize=14, pad=20)
            ax.axis('equal')  # Equal aspect ratio ensures pie is drawn as circle
            
            # Add percentage and count in center
            # center_text = f'Total Responses\n{total_responses}'
            # ax.text(0, 0, center_text, 
            #     ha='center', va='center', 
            #     fontsize=12, color='#2c3e50')

        else:
            # Bar chart for single feedback type
            ax = fig.add_subplot(111)
            feedback_type = 'Direct' if has_direct else 'Indirect'
            avg_score = self.convert_to_percentage(
                direct_data['response'] if has_direct else indirect_data['response']
            )

            bars = ax.bar([feedback_type], [avg_score], 
                        color='#3498db', width=0.6)
            ax.set_ylim(0, 100)
            ax.set_ylabel('Average Score (%)')
            ax.set_title(f'{feedback_type} Feedback Score', fontsize=14)
            
            # Add value label
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.1f}%', ha='center', va='bottom', fontsize=12)

        # self.overall_canvas.tight_layout()
        fig.tight_layout()

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

    # def update_question_analysis(self, question_text):
    #     fig = self.question_canvas.figure
    #     fig.clear()
        
    #     if not question_text:
    #         return
            
    #     question_id = self.question_combo.currentData()
    #     question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
        
    #     if question_data.empty:
    #         ax = fig.add_subplot(111)
    #         ax.text(0.5, 0.5, 'No data available\nfor this question', 
    #                ha='center', va='center', fontsize=12)
    #         self.question_canvas.draw()
    #         return
        
    #     # Prepare data
    #     response_counts = question_data['response'].value_counts().sort_index()
    #     options = [f"Option {i}" for i in range(1, 5)]
    #     counts = [response_counts.get(str(i), 0) for i in range(1, 5)]
    #     total = sum(counts)
    #     percentages = [(count/total)*100 if total > 0 else 0 for count in counts]
        
    #     # Create donut chart
    #     ax = fig.add_subplot(111)
    #     wedges, texts, autotexts = ax.pie(
    #         percentages,
    #         labels=options,
    #         autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
    #         startangle=90,
    #         colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
    #         wedgeprops={'width': 0.4, 'edgecolor': 'white'},
    #         textprops={'fontsize': 10}
    #     )
        
    #     # Add center circle
    #     # centre_circle = plt.Circle((0,0), 0.2, fc='white')
    #     # ax.add_artist(centre_circle)
        
    #     # Add question text
    #     ax.set_title(question_text, fontsize=12, pad=20, color='#2c3e50')
        
    #     # Style legend
    #     legend = ax.legend(
    #         wedges,
    #         [f"Option {i+1}" for i in range(4)],
    #         title="Response Options",
    #         loc="center",
    #         bbox_to_anchor=(0.5, -0.1),
    #         ncol=4
    #     )
    #     legend.get_title().set_fontsize(10)
        
    #     # Style percentages
    #     for autotext in autotexts:
    #         autotext.set_color('white')
    #         autotext.set_fontweight('bold')
        
    #     self.question_canvas.draw()

    # def update_question_analysis(self, question_text):
    #     fig = self.question_canvas.figure
    #     fig.clear()
        
    #     # if not question_text:
    #     #     return
    #     if not question_text or self.merged_data.empty:
    #         ax = fig.add_subplot(111)
    #         ax.text(0.5, 0.5, 'No data available', 
    #                ha='center', va='center', fontsize=12)
    #         self.question_canvas.draw()
    #         return
            
    #     question_id = self.question_combo.currentData()
    #     question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
        
    #     if question_data.empty:
    #         ax = fig.add_subplot(111)
    #         ax.text(0.5, 0.5, 'No data available\nfor this question', 
    #             ha='center', va='center', fontsize=12)
    #         self.question_canvas.draw()
    #         return
        
    #     try:
    #         # Convert responses to numeric and handle NaNs
    #         question_data = question_data.dropna(subset=['response'])
    #         response_counts = question_data['response'].astype(int).value_counts().sort_index()
            
    #         # Ensure we have all possible options (1-4)
    #         response_counts = response_counts.reindex([1, 2, 3, 4], fill_value=0)
    #         total = response_counts.sum()
            
    #         if total == 0:
    #             raise ValueError("No valid responses")
                
    #         percentages = (response_counts / total) * 100
            
    #         # Create donut chart
    #         ax = fig.add_subplot(111)
    #         wedges, texts, autotexts = ax.pie(
    #             percentages,
    #             labels=[f"Option {i}" for i in range(1, 5)],
    #             autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
    #             startangle=90,
    #             colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
    #             wedgeprops={'width': 0.4, 'edgecolor': 'white'},
    #             textprops={'fontsize': 10}
    #         )
            
    #         # Add center circle
    #         # centre_circle = plt.Circle((0,0), 0.2, fc='white')
    #         # ax.add_artist(centre_circle)
    #         ax.set_title(question_text, fontsize=12, pad=20)
    #             #     # Add question text
    #         # ax.set_title(question_text, fontsize=12, pad=20, color='#2c3e50')
            
    #         # Style legend
    #         legend = ax.legend(
    #             wedges,
    #             [f"Option {i+1}" for i in range(4)],
    #             title="Response Options",
    #             loc="center",
    #             bbox_to_anchor=(0.5, -0.1),
    #             ncol=4
    #         )
    #         legend.get_title().set_fontsize(10)
            
    #         # Style percentages
    #         for autotext in autotexts:
    #             autotext.set_color('white')
    #             autotext.set_fontweight('bold')
            
    #         self.question_canvas.draw()
            
    #     except Exception as e:
    #         ax = fig.add_subplot(111)
    #         ax.text(0.5, 0.5, 'Error displaying data\nPlease check input', 
    #             ha='center', va='center', fontsize=12, color='red')
            
    #         self.question_canvas.draw()

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

            # def plot_pie(ax, data, title):
            #     if data.empty:
            #         ax.axis('off')
            #         return
                    
            #     question_id = self.question_combo.currentData()
            #     question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
            #     options = [
            #         question_row['Option1'],
            #         question_row['Option2'],
            #         question_row['Option3'],
            #         question_row['Option4']
            #     ]

            #     response_counts = data['response'].astype(int).value_counts().sort_index()
            #     response_counts = response_counts.reindex([1, 2, 3, 4], fill_value=0)
            #     total = response_counts.sum()
                
            #     if total == 0:
            #         ax.axis('off')
            #         return
                    
            #     percentages = (response_counts / total) * 100
                
            #     # Create custom labels with conditional display
            #     labels = [
            #         f"{opt[:15]}..." if len(opt) > 15 else opt 
            #         for opt in options
            #     ]
                
            #     wedges, texts, autotexts = ax.pie(
            #         percentages,
            #         startangle=90,
            #         colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
            #         wedgeprops={'width': 0.4, 'edgecolor': 'white', 'linewidth': 0.5},
            #         textprops={'fontsize': 8, 'color': 'white'},
            #         pctdistance=0.85  # Move percentage text inward
            #     )
                
            #     # Custom percentage labels with conditional display
            #     for i, (pct, autotext) in enumerate(zip(percentages, autotexts)):
            #         autotext.set_visible(pct >= 5)  # Only show percentages ≥5%
            #         autotext.set_text(f'{pct:.0f}%' if pct >= 5 else '')
                
            #     ax.set_title(title, fontsize=10, pad=12)
                
            #     # Create enhanced legend
            #     legend_labels = [
            #         f"{label}\n({pct:.1f}%)" if pct >= 1 else ""
            #         for label, pct in zip(labels, percentages)
            #     ]
                
            #     legend = ax.legend(
            #         wedges,
            #         legend_labels,
            #         title="Response Options",
            #         loc="upper center",
            #         bbox_to_anchor=(0.5, -0.15),
            #         ncol=2,
            #         frameon=False,
            #         fontsize=8,
            #         title_fontsize=9,
            #         handletextpad=0.3,
            #         columnspacing=0.5
            #     )
                
            #     # Add percentage badges
            #     for text, pct in zip(legend.get_texts(), percentages):
            #         if pct < 1:
            #             text.set_visible(False)

            # def plot_pie(ax, data, title):
            #     if data.empty:
            #         ax.axis('off')
            #         return
                    
            #     # Get actual question options from Excel data
            #     question_id = self.question_combo.currentData()
            #     question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
            #     options = [
            #         question_row['Option1'],
            #         question_row['Option2'],
            #         question_row['Option3'],
            #         question_row['Option4']
            #     ]

            #     response_counts = data['response'].astype(int).value_counts().sort_index()
            #     response_counts = response_counts.reindex([1, 2, 3, 4], fill_value=0)
            #     total = response_counts.sum()
                
            #     if total == 0:
            #         ax.axis('off')
            #         return
                    
            #     percentages = (response_counts / total) * 100
                
            #     # wedges, texts, autotexts = ax.pie(
            #     #     percentages,
            #     #     labels=options,  # Use actual options here
            #     #     autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
            #     #     startangle=90,
            #     #     colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
            #     #     wedgeprops={'width': 0.4, 'edgecolor': 'white'},
            #     #     textprops={'fontsize': 10}
            #     # )
            #     wedges, texts, autotexts = ax.pie(
            #         percentages,
            #         labels=options,
            #         autopct=lambda p: f'{p:.1f}%' if p >= 25 else '',
            #         startangle=90,
            #         colors=['#e74c3c', '#3498db', '#2ecc71', '#f1c40f'],
            #         wedgeprops={'width': 0.4, 'edgecolor': 'white'},
            #         textprops={'fontsize': 8}  # Reduced font size
            #     )
                
            #     ax.set_title(title, fontsize=12, pad=20)
                
            #     # Update legend with actual options
            #     legend = ax.legend(
            #         wedges,
            #         options,  # Use actual options here
            #         title="Response Options",
            #         loc="center",
            #         bbox_to_anchor=(0.5, -0.1),
            #         ncol=2  # Changed to 2 columns for better fit
            #     )
            #     legend.get_title().set_fontsize(10)
                
            #     for autotext in autotexts:
            #         autotext.set_color('white')
            #         autotext.set_fontweight('bold')

            def plot_pie(ax, data, title):
                if data.empty:
                    ax.axis('off')
                    return
                    
                # Get question data
                question_id = self.question_combo.currentData()
                question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
                options = [
                    question_row['Option1'],
                    question_row['Option2'],
                    question_row['Option3'],
                    question_row['Option4']
                ]

                response_counts = data['response'].astype(int).value_counts().sort_index()
                response_counts = response_counts.reindex([1, 2, 3, 4], fill_value=0)
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