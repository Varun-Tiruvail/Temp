import sys
import os
import glob
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QDialog, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QStackedWidget, QComboBox,
    QTabWidget, QScrollArea, QRadioButton, QButtonGroup, QTextEdit,
    QTableWidget, QTableWidgetItem, QHeaderView, QGroupBox, QSplitter,
    QCheckBox, QFormLayout, QGridLayout
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
import matplotlib
from matplotlib import cm
import datetime
matplotlib.use('Qt5Agg')

# Configuration Constants
MIN_REPORTEES_FOR_SCORECHART = 2
DATABASE_NAME = "feedback_system.db"

# Database Initialization Functions
def initialize_databases():
    """Initialize the database structure and sample data"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        manager TEXT,
        is_superuser INTEGER DEFAULT 0,
        is_approved INTEGER DEFAULT 0
    )
    ''')
    
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS feedback (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        feedback_type TEXT NOT NULL,
        question_id TEXT,
        category TEXT,
        response_value INTEGER,
        response_text TEXT,
        timestamp TEXT,
        is_aggregated INTEGER DEFAULT 0,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    ''')
    
    # Create sample hierarchy if it doesn't exist
    if not os.path.exists('employee_hierarchy.xlsx'):
        hierarchy_data = {
            'Manager': ['Admin', 'Admin', 'Manager1', 'Manager1', 'Manager2'],
            'Reportee': ['Manager1', 'Manager2', 'Employee1', 'Employee2', 'Employee3']
        }
        pd.DataFrame(hierarchy_data).to_excel('employee_hierarchy.xlsx', index=False)
    
    # Create sample questions if they don't exist
    if not os.path.exists('survey_questions.xlsx'):
        questions = [
            {
                'QuestionID': 'CULT1', 'Category': 'Cultural',
                'Question': 'Promotes inclusive and diverse workplace',
                'Option1': 'Rarely (1)', 'Option2': 'Sometimes (2)',
                'Option3': 'Often (3)', 'Option4': 'Always (4)'
            },
            {
                'QuestionID': 'CULT2', 'Category': 'Cultural',
                'Question': 'Encourages collaboration and teamwork',
                'Option1': 'Rarely (1)', 'Option2': 'Sometimes (2)',
                'Option3': 'Often (3)', 'Option4': 'Always (4)'
            }
        ]
        pd.DataFrame(questions).to_excel('survey_questions.xlsx', index=False)
    
    # Add admin user if not exists
    cursor.execute("SELECT * FROM users WHERE username='Admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, manager, is_superuser, is_approved) VALUES (?, ?, ?, ?, ?)",
            ('Admin', 'admin123', 'None', 1, 1)
        )
    
    conn.commit()
    conn.close()

def get_reportee_count(username):
    """Count direct reportees for a user"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        return len(df[df['Manager'] == username]['Reportee'].unique())
    except Exception as e:
        print(f"Error counting reportees: {e}")
        return 0

def get_manager(username):
    """Get manager for a given username"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        manager = df[df['Reportee'] == username]['Manager'].values
        return manager[0] if len(manager) > 0 else None
    except Exception as e:
        print(f"Error getting manager: {e}")
        return None

def validate_login(username, password):
    """Validate user credentials"""
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username, manager, is_superuser FROM users WHERE username=? AND password=? AND is_approved=1",
        (username, password)
    )
    user = cursor.fetchone()
    if user:
        reportee_count = get_reportee_count(username)
        return (*user, reportee_count)  # Returns tuple (id, username, manager, is_superuser, reportee_count)
    conn.close()
    return None

class AuthWindow(QWidget):
    def __init__(self, on_login_success):
        super().__init__()
        self.on_login_success = on_login_success
        initialize_databases()
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Employee Feedback System - Authentication')
        self.setFixedSize(400, 300)
        
        self.stacked_widget = QStackedWidget()
        
        # Login Page
        self.login_page = QWidget()
        self.setup_login_page()
        
        # Register Page
        self.register_page = QWidget()
        self.setup_register_page()
        
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        
        layout = QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)
    
    def setup_login_page(self):
        layout = QVBoxLayout()
        
        title = QLabel('Login')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        
        layout.addWidget(QLabel('Username:'))
        self.login_username = QLineEdit()
        layout.addWidget(self.login_username)
        
        layout.addWidget(QLabel('Password:'))
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.login_password)
        
        login_btn = QPushButton('Login')
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)
        
        switch_btn = QPushButton('Need an account? Register')
        switch_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addWidget(switch_btn)
        
        self.login_page.setLayout(layout)
    
    def setup_register_page(self):
        layout = QVBoxLayout()
        
        title = QLabel('Register')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        
        layout.addWidget(QLabel('Username:'))
        self.register_username = QLineEdit()
        layout.addWidget(self.register_username)
        
        layout.addWidget(QLabel('Password:'))
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.register_password)
        
        layout.addWidget(QLabel('Confirm Password:'))
        self.register_confirm_password = QLineEdit()
        self.register_confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.register_confirm_password)
        
        register_btn = QPushButton('Register')
        register_btn.clicked.connect(self.handle_register)
        layout.addWidget(register_btn)
        
        switch_btn = QPushButton('Already have an account? Login')
        switch_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        layout.addWidget(switch_btn)
        
        self.register_page.setLayout(layout)
    
    def handle_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Please enter both username and password')
            return
        
        user = validate_login(username, password)
        if user:
            self.on_login_success(user[1], user[2], bool(user[3]), user[4])
        else:
            QMessageBox.warning(self, 'Error', 'Invalid username or password')
    
    def handle_register(self):
        username = self.register_username.text().strip()
        password = self.register_password.text().strip()
        confirm_password = self.register_confirm_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Please enter both username and password')
            return
        
        if password != confirm_password:
            QMessageBox.warning(self, 'Error', 'Passwords do not match')
            return
        
        manager = get_manager(username)
        if not manager:
            QMessageBox.warning(self, 'Error', 'Username not found in company hierarchy')
            return
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password, manager, is_approved) VALUES (?, ?, ?, ?)",
                (username, password, manager, 0)
            )
            conn.commit()
            QMessageBox.information(
                self, 'Success', 
                'Registration submitted for approval. Your manager will review your request.'
            )
            self.stacked_widget.setCurrentIndex(0)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, 'Error', 'Username already exists')
        finally:
            conn.close()

# class SurveyApp(QDialog):
#     def __init__(self, current_user, manager_name):
#         super().__init__()
#         self.current_user = current_user
#         self.manager_name = manager_name
#         self.setWindowTitle(f"Feedback Survey - {current_user}")
#         self.resize(1000, 800)  # Increased size to accommodate more tabs
#         self.questions_df = self.load_questions()
#         self.lm_responses = {}
#         self.init_ui()
    
#     def load_questions(self):
#         try:
#             df = pd.read_excel('survey_questions.xlsx')
#             required_columns = ['QuestionID', 'Category', 'Question', 'Option1', 'Option2', 'Option3', 'Option4']
#             if not all(col in df.columns for col in required_columns):
#                 raise ValueError("Missing required columns in questions file")
#             return df
#         except Exception as e:
#             QMessageBox.critical(self, "Error", f"Failed to load questions: {str(e)}")
#             sys.exit(1)
    
#     def init_ui(self):
#         main_layout = QVBoxLayout()
        
#         # Create main tab widget
#         self.main_tab_widget = QTabWidget()
        
#         # Create the category tabs (Cultural, Developmental, Ways of Working)
#         self.create_category_tabs()
        
#         # Create other tabs (General Feedback and Summary)
#         self.create_general_feedback_tab()
#         self.create_summary_tab()
        
#         # Add all tabs to the main tab widget
#         self.main_tab_widget.addTab(self.category_tabs, "Manager Feedback")
#         self.main_tab_widget.addTab(self.general_feedback_tab, "General Feedback")
#         self.main_tab_widget.addTab(self.summary_tab, "Summary")
        
#         main_layout.addWidget(self.main_tab_widget)
        
#         # Submit button
#         self.submit_button = QPushButton("Submit Feedback")
#         self.submit_button.setStyleSheet(
#             "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }"
#             "QPushButton:hover { background-color: #45a049; }"
#         )
#         self.submit_button.clicked.connect(self.submit_feedback)
#         main_layout.addWidget(self.submit_button)
        
#         self.setLayout(main_layout)
    
#     def create_category_tabs(self):
#         """Create a tab widget with tabs for each category"""
#         self.category_tabs = QTabWidget()
        
#         # Create tabs for each category
#         categories = {
#             'Cultural': self.create_cultural_tab(),
#             'Developmental': self.create_developmental_tab(),
#             'Ways of Working': self.create_ways_of_working_tab()
#         }
        
#         # Add tabs for categories that have questions
#         for category_name, tab_widget in categories.items():
#             if tab_widget is not None:  # Only add tab if there are questions for this category
#                 self.category_tabs.addTab(tab_widget, category_name)
    
#     def create_category_tab(self, category_name):
#         """Helper method to create a tab for a specific category"""
#         questions = self.questions_df[self.questions_df['Category'] == category_name]
#         if questions.empty:
#             return None  # Return None if no questions for this category
        
#         tab = QWidget()
#         layout = QVBoxLayout()
        
#         scroll = QScrollArea()
#         scroll.setWidgetResizable(True)
#         container = QWidget()
#         container_layout = QVBoxLayout()
        
#         # Add questions for this category
#         for _, row in questions.iterrows():
#             q_id = row['QuestionID']
#             question_text = row['Question']
            
#             question_group = QGroupBox(question_text)
#             question_layout = QVBoxLayout()
            
#             # Create radio buttons for options
#             option_group = QButtonGroup(self)
#             self.lm_responses[q_id] = None
            
#             for i in range(1, 5):
#                 option_text = row[f'Option{i}']
#                 radio = QRadioButton(option_text)
#                 radio.setObjectName(f"{q_id}_{i}")
#                 radio.toggled.connect(lambda checked, q=q_id, v=i: self.set_response(q, v) if checked else None)
#                 option_group.addButton(radio)
#                 question_layout.addWidget(radio)
            
#             question_group.setLayout(question_layout)
#             container_layout.addWidget(question_group)
        
#         container.setLayout(container_layout)
#         scroll.setWidget(container)
#         layout.addWidget(scroll)
#         tab.setLayout(layout)
        
#         return tab
    
#     def create_cultural_tab(self):
#         """Create the Cultural questions tab"""
#         return self.create_category_tab('Cultural')
    
#     def create_developmental_tab(self):
#         """Create the Developmental questions tab"""
#         return self.create_category_tab('Developmental')
    
#     def create_ways_of_working_tab(self):
#         """Create the Ways of Working questions tab"""
#         return self.create_category_tab('Ways of Working')
    
#     def create_general_feedback_tab(self):
#         """Create the general feedback tab with a text input area"""
#         self.general_feedback_tab = QWidget()
#         layout = QVBoxLayout()
        
#         label = QLabel("Please provide any general feedback or concerns:")
#         layout.addWidget(label)
        
#         self.general_feedback_input = QTextEdit()
#         self.general_feedback_input.setPlaceholderText("Type your feedback here...")
#         layout.addWidget(self.general_feedback_input)
        
#         self.general_feedback_tab.setLayout(layout)
    
#     def create_summary_tab(self):
#         """Create the summary tab showing all responses before submission"""
#         self.summary_tab = QWidget()
#         layout = QVBoxLayout()
        
#         # Manager feedback summary
#         manager_summary_group = QGroupBox("Manager Feedback Summary")
#         manager_summary_layout = QVBoxLayout()
        
#         self.manager_summary_text = QTextEdit()
#         self.manager_summary_text.setReadOnly(True)
#         manager_summary_layout.addWidget(self.manager_summary_text)
        
#         manager_summary_group.setLayout(manager_summary_layout)
#         layout.addWidget(manager_summary_group)
        
#         # General feedback summary
#         general_summary_group = QGroupBox("General Feedback Summary")
#         general_summary_layout = QVBoxLayout()
        
#         self.general_summary_text = QTextEdit()
#         self.general_summary_text.setReadOnly(True)
#         general_summary_layout.addWidget(self.general_summary_text)
        
#         general_summary_group.setLayout(general_summary_layout)
#         layout.addWidget(general_summary_group)
        
#         # Update summaries when tab is shown
#         self.main_tab_widget.currentChanged.connect(self.update_summary_tab)
        
#         self.summary_tab.setLayout(layout)
    
#     def set_response(self, question_id, value):
#         self.lm_responses[question_id] = value
    
#     def update_summary_tab(self, index):
#         """Update the summary tab when it's selected"""
#         if self.main_tab_widget.widget(index) == self.summary_tab:
#             # Update manager feedback summary
#             manager_summary = []
#             for q_id, response in self.lm_responses.items():
#                 if response is not None:
#                     question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
#                     manager_summary.append(
#                         f"Category: {question_data['Category']}\n"
#                         f"Q: {question_data['Question']}\n"
#                         f"A: {question_data[f'Option{response}']}\n"
#                         f"{'-'*40}\n"
#                     )
            
#             if manager_summary:
#                 self.manager_summary_text.setPlainText("\n".join(manager_summary))
#             else:
#                 self.manager_summary_text.setPlainText("No manager feedback provided yet")
            
#             # Update general feedback summary
#             general_feedback = self.general_feedback_input.toPlainText().strip()
#             if general_feedback:
#                 self.general_summary_text.setPlainText(general_feedback)
#             else:
#                 self.general_summary_text.setPlainText("No general feedback provided yet")
    
#     def submit_feedback(self):
#         conn = sqlite3.connect(DATABASE_NAME)
#         cursor = conn.cursor()
        
#         try:
#             # Get user ID
#             cursor.execute("SELECT id FROM users WHERE username=?", (self.current_user,))
#             user_id = cursor.fetchone()[0]
#             timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
#             # Process manager feedback
#             for q_id, response in self.lm_responses.items():
#                 if response is not None:
#                     question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
#                     cursor.execute(
#                         '''INSERT INTO feedback 
#                         (user_id, feedback_type, question_id, category, response_value, response_text, timestamp)
#                         VALUES (?, ?, ?, ?, ?, ?, ?)''',
#                         (user_id, 'LM', q_id, question_data['Category'], response,
#                          question_data[f'Option{response}'], timestamp)
#                     )
            
#             # Process general feedback
#             general_feedback = self.general_feedback_input.toPlainText().strip()
#             if general_feedback:
#                 cursor.execute(
#                     '''INSERT INTO feedback 
#                     (user_id, feedback_type, response_text, timestamp)
#                     VALUES (?, ?, ?, ?)''',
#                     (user_id, 'General', general_feedback, timestamp)
#                 )
            
#             # If user has a manager, create aggregated feedback entry
#             if self.manager_name and self.manager_name.lower() != 'none':
#                 cursor.execute(
#                     '''INSERT INTO feedback 
#                     (user_id, feedback_type, response_text, timestamp, is_aggregated)
#                     VALUES (?, ?, ?, ?, ?)''',
#                     (user_id, 'Aggregate', f"Feedback submission from {self.current_user}", timestamp, 1)
#                 )
            
#             conn.commit()
#             QMessageBox.information(self, "Success", "Feedback submitted successfully!")
#             self.close()
            
#         except Exception as e:
#             conn.rollback()
#             QMessageBox.critical(self, "Error", f"Failed to submit feedback: {str(e)}")
#         finally:
#             conn.close()

class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.setWindowTitle(f"Feedback Survey - {current_user}")
        self.resize(1000, 800)
        self.questions_df = self.load_questions()
        self.lm_responses = {}
        self.init_ui()
    
    def load_questions(self):
        try:
            df = pd.read_excel('survey_questions.xlsx')
            required_columns = ['QuestionID', 'Category', 'Question', 'Option1', 'Option2', 'Option3', 'Option4']
            if not all(col in df.columns for col in required_columns):
                raise ValueError("Missing required columns in questions file")
            
            # Ensure all categories are properly formatted
            df['Category'] = df['Category'].str.strip().str.title()
            return df
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load questions: {str(e)}")
            sys.exit(1)
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Create main tab widget
        self.main_tab_widget = QTabWidget()
        
        # Create the category tabs
        self.create_category_tabs()
        
        # Create other tabs
        self.create_general_feedback_tab()
        self.create_summary_tab()
        
        # Add all tabs to the main tab widget
        if self.category_tabs.count() > 0:  # Only add if we have category tabs
            self.main_tab_widget.addTab(self.category_tabs, "Manager Feedback")
        self.main_tab_widget.addTab(self.general_feedback_tab, "General Feedback")
        self.main_tab_widget.addTab(self.summary_tab, "Summary")
        
        main_layout.addWidget(self.main_tab_widget)
        
        # Submit button
        self.submit_button = QPushButton("Submit Feedback")
        self.submit_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.submit_button.clicked.connect(self.submit_feedback)
        main_layout.addWidget(self.submit_button)
        
        self.setLayout(main_layout)
    
    def create_category_tabs(self):
        """Create a tab widget with tabs for each existing category"""
        self.category_tabs = QTabWidget()
        
        # Get unique categories from questions
        existing_categories = self.questions_df['Category'].unique()
        
        # Standard categories we want to check for
        standard_categories = ['Cultural', 'Development', 'Ways Of Working']
        
        # Create tabs for each standard category that exists in our questions
        for category in standard_categories:
            # Find matching category (case-insensitive)
            matching_categories = [c for c in existing_categories if c.lower() == category.lower()]
            
            if matching_categories:
                actual_category = matching_categories[0]  # Use the actual category name from the data
                tab = self.create_category_tab(actual_category)
                if tab:  # Only add tab if it has questions
                    self.category_tabs.addTab(tab, category)  # Use standard name for tab
        
        # If no standard categories found but we have other categories, create tabs for them
        if self.category_tabs.count() == 0 and len(existing_categories) > 0:
            for category in existing_categories:
                tab = self.create_category_tab(category)
                if tab:
                    self.category_tabs.addTab(tab, category)
    
    def create_category_tab(self, category_name):
        """Create a tab for a specific category"""
        questions = self.questions_df[self.questions_df['Category'].str.lower() == category_name.lower()]
        
        if questions.empty:
            return None
        
        tab = QWidget()
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout()
        
        for _, row in questions.iterrows():
            q_id = row['QuestionID']
            question_text = row['Question']
            
            question_group = QGroupBox(question_text)
            question_layout = QVBoxLayout()
            
            option_group = QButtonGroup(self)
            self.lm_responses[q_id] = None
            
            for i in range(1, 5):
                option_text = row[f'Option{i}']
                radio = QRadioButton(option_text)
                radio.setObjectName(f"{q_id}_{i}")
                radio.toggled.connect(lambda checked, q=q_id, v=i: self.set_response(q, v) if checked else None)
                option_group.addButton(radio)
                question_layout.addWidget(radio)
            
            question_group.setLayout(question_layout)
            container_layout.addWidget(question_group)
        
        container.setLayout(container_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        tab.setLayout(layout)
        
        return tab
    
    def create_general_feedback_tab(self):
        """Create the general feedback tab"""
        self.general_feedback_tab = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Please provide any general feedback or concerns:")
        layout.addWidget(label)
        
        self.general_feedback_input = QTextEdit()
        self.general_feedback_input.setPlaceholderText("Type your feedback here...")
        layout.addWidget(self.general_feedback_input)
        
        self.general_feedback_tab.setLayout(layout)
    
    def create_summary_tab(self):
        """Create the summary tab"""
        self.summary_tab = QWidget()
        layout = QVBoxLayout()
        
        manager_summary_group = QGroupBox("Manager Feedback Summary")
        manager_summary_layout = QVBoxLayout()
        self.manager_summary_text = QTextEdit()
        self.manager_summary_text.setReadOnly(True)
        manager_summary_layout.addWidget(self.manager_summary_text)
        manager_summary_group.setLayout(manager_summary_layout)
        layout.addWidget(manager_summary_group)
        
        general_summary_group = QGroupBox("General Feedback Summary")
        general_summary_layout = QVBoxLayout()
        self.general_summary_text = QTextEdit()
        self.general_summary_text.setReadOnly(True)
        general_summary_layout.addWidget(self.general_summary_text)
        general_summary_group.setLayout(general_summary_layout)
        layout.addWidget(general_summary_group)
        
        self.main_tab_widget.currentChanged.connect(self.update_summary_tab)
        self.summary_tab.setLayout(layout)
    
    def set_response(self, question_id, value):
        self.lm_responses[question_id] = value
    
    def update_summary_tab(self, index):
        if self.main_tab_widget.widget(index) == self.summary_tab:
            manager_summary = []
            for q_id, response in self.lm_responses.items():
                if response is not None:
                    question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
                    manager_summary.append(
                        f"Category: {question_data['Category']}\n"
                        f"Q: {question_data['Question']}\n"
                        f"A: {question_data[f'Option{response}']}\n"
                        f"{'-'*40}\n"
                    )
            
            self.manager_summary_text.setPlainText("\n".join(manager_summary) if manager_summary else "No manager feedback provided yet")
            general_feedback = self.general_feedback_input.toPlainText().strip()
            self.general_summary_text.setPlainText(general_feedback if general_feedback else "No general feedback provided yet")
    
    # def submit_feedback(self):
    #     conn = sqlite3.connect(DATABASE_NAME)
    #     cursor = conn.cursor()
        
    #     try:
    #         cursor.execute("SELECT id FROM users WHERE username=?", (self.current_user,))
    #         user_id = cursor.fetchone()[0]
    #         timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
    #         for q_id, response in self.lm_responses.items():
    #             if response is not None:
    #                 question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
    #                 cursor.execute(
    #                     '''INSERT INTO feedback 
    #                     (user_id, feedback_type, question_id, category, response_value, response_text, timestamp)
    #                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
    #                     (user_id, 'LM', q_id, question_data['Category'], response,
    #                      question_data[f'Option{response}'], timestamp)
    #                 )
            
    #         general_feedback = self.general_feedback_input.toPlainText().strip()
    #         if general_feedback:
    #             cursor.execute(
    #                 '''INSERT INTO feedback 
    #                 (user_id, feedback_type, response_text, timestamp)
    #                 VALUES (?, ?, ?, ?)''',
    #                 (user_id, 'General', general_feedback, timestamp)
    #             )
            
    #         if self.manager_name and self.manager_name.lower() != 'none':
    #             cursor.execute(
    #                 '''INSERT INTO feedback 
    #                 (user_id, feedback_type, response_text, timestamp, is_aggregated)
    #                 VALUES (?, ?, ?, ?, ?)''',
    #                 (user_id, 'Aggregate', f"Feedback submission from {self.current_user}", timestamp, 1)
    #             )
            
    #         conn.commit()
    #         QMessageBox.information(self, "Success", "Feedback submitted successfully!")
    #         self.close()
            
    #     except Exception as e:
    #         conn.rollback()
    #         QMessageBox.critical(self, "Error", f"Failed to submit feedback: {str(e)}")
    #     finally:
    #         conn.close()

    def submit_feedback(self):
        # Get user ID first
        user_id = self.get_user_id()  # You'll need to implement this
        
        # Submit manager feedback
        for q_id, response in self.lm_responses.items():
            if response is not None:
                question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
                self.analysis_app.submit_feedback(
                    user_id, 'LM', q_id, question_data['Category'], 
                    response, question_data[f'Option{response}']
                )
        
        # Submit general feedback
        general_feedback = self.general_feedback_input.toPlainText().strip()
        if general_feedback:
            self.analysis_app.submit_feedback(
                user_id, 'General', response_text=general_feedback
            )
        
        QMessageBox.information(self, "Success", "Feedback submitted confidentially!")
        self.close()

class AnalysisApp(QDialog):
    def __init__(self, current_user, manager_name, is_superuser=False, reportee_count=0):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.is_superuser = is_superuser
        self.reportee_count = reportee_count
        self.viewing_team_data = False
        self.MIN_REPORTEES_FOR_SCORECHART = 2  # Make this configurable if needed
        self.SCOREDATA_FOLDER = "scoredata"
        self.feedback_df = pd.DataFrame()
        self.manager_feedback_df = pd.DataFrame()
        
        self.setWindowTitle(f"Survey Analysis - {current_user}")
        self.resize(1200, 900)
        
        # Create scoredata folder if it doesn't exist
        os.makedirs(self.SCOREDATA_FOLDER, exist_ok=True)
        
        # Check if score chart should be visible
        self.score_chart_visible = (self.is_superuser or 
                                  self.reportee_count >= self.MIN_REPORTEES_FOR_SCORECHART)
        
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions: {str(e)}")
            sys.exit(1)
            
        self.init_ui()
        self.load_data()

    def get_feedback_db_path(self, manager_name):
        """Generate the database path for a manager's feedback"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return os.path.join(self.SCOREDATA_FOLDER, f"{manager_name}_{timestamp}.db")

    def load_data(self):
        try:
            # Load feedback for current user (manager)
            if self.score_chart_visible:
                db_path = self.get_feedback_db_path(self.current_user)
                if os.path.exists(db_path):
                    self.feedback_df = self.load_feedback_from_db(db_path)
                else:
                    self.feedback_df = pd.DataFrame()
            
            # For managers with few reportees, load their manager's feedback
            if not self.is_superuser and self.reportee_count < self.MIN_REPORTEES_FOR_SCORECHART and self.manager_name:
                manager_db_path = self.get_feedback_db_path(self.manager_name)
                if os.path.exists(manager_db_path):
                    self.manager_feedback_df = self.load_feedback_from_db(manager_db_path)
                    # Filter only indirect feedback meant for this user
                    self.manager_feedback_df = self.manager_feedback_df[
                        self.manager_feedback_df['response_text'].str.contains(f"indirect feedback for {self.current_user}", case=False)
                    ]
                else:
                    self.manager_feedback_df = pd.DataFrame()
            
            # Update displays
            if not self.feedback_df.empty or not self.manager_feedback_df.empty:
                self.update_analyses()
            else:
                self.show_no_data_message()
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def load_feedback_from_db(self, db_path):
        """Load feedback data from a specific database file"""
        conn = sqlite3.connect(db_path)
        try:
            query = """
            SELECT f.*, u.username 
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            WHERE f.is_aggregated = 0
            """
            df = pd.read_sql_query(query, conn)
            
            # For general feedback, anonymize the usernames
            df.loc[df['feedback_type'] == 'General', 'username'] = 'Anonymous'
            
            return df
        finally:
            conn.close()

    def submit_feedback(self, user_id, feedback_type, question_id=None, category=None, 
                       response_value=None, response_text=None, is_aggregated=False):
        """Submit feedback to the appropriate database file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Determine which database to use
        if feedback_type == 'LM' and not is_aggregated:
            # Line manager feedback goes to the manager's database
            manager_name = self.manager_name if not self.viewing_team_data else self.current_user
            db_path = self.get_feedback_db_path(manager_name)
        else:
            # General feedback goes to current user's database
            db_path = self.get_feedback_db_path(self.current_user)
        
        # Create database if it doesn't exist
        if not os.path.exists(db_path):
            self.initialize_feedback_db(db_path)
        
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO feedback 
                (user_id, feedback_type, question_id, category, response_value, response_text, timestamp, is_aggregated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id, feedback_type, question_id, category, 
                response_value, response_text, timestamp, is_aggregated
            ))
            conn.commit()
        finally:
            conn.close()
        
        # For managers with few reportees, create indirect feedback for their manager
        if (feedback_type == 'LM' and not self.is_superuser and 
            self.reportee_count < self.MIN_REPORTEES_FOR_SCORECHART and 
            self.manager_name and not is_aggregated):
            
            indirect_text = f"Indirect feedback for {self.current_user}: {response_text}"
            self.submit_feedback(
                user_id, 'Indirect', question_id, category, 
                response_value, indirect_text, True
            )

    def initialize_feedback_db(self, db_path):
        """Initialize a new feedback database file"""
        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            
            # Create tables (same structure as your original database)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    manager TEXT,
                    is_superuser INTEGER DEFAULT 0,
                    is_approved INTEGER DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    feedback_type TEXT NOT NULL,
                    question_id TEXT,
                    category TEXT,
                    response_value INTEGER,
                    response_text TEXT,
                    timestamp TEXT,
                    is_aggregated INTEGER DEFAULT 0,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                )
            ''')
            
            conn.commit()
        finally:
            conn.close()

    def show_no_data_message(self):
        """Show appropriate message when no data is available"""
        if hasattr(self, 'overall_canvas'):
            self.overall_canvas.figure.clear()
            ax = self.overall_canvas.figure.add_subplot(111)
            
            if not self.score_chart_visible and self.reportee_count < self.MIN_REPORTEES_FOR_SCORECHART:
                msg = (f"Score chart requires at least {self.MIN_REPORTEES_FOR_SCORECHART} reportees.\n"
                      f"You have {self.reportee_count}. Your feedback has been\n"
                      f"included in your manager's analysis.")
            else:
                msg = "No feedback data available"
            
            ax.text(0.5, 0.5, msg, ha='center', va='center')
            self.overall_canvas.draw()
        
        # Similar clearing for other canvases...
        if hasattr(self, 'section_canvas'):
            self.section_canvas.figure.clear()
            self.section_canvas.draw()
        
        if hasattr(self, 'question_canvas'):
            self.question_canvas.figure.clear()
            self.question_canvas.draw()
        
        if hasattr(self, 'general_feedback_display'):
            self.general_feedback_display.setPlainText("No general feedback available")
        
        if hasattr(self, 'indirect_feedback_display'):
            self.indirect_feedback_display.setPlainText("No indirect feedback available")
        
        self.status_label.setText("No feedback data found for current view")

    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Header
        header_layout = QHBoxLayout()
        role_info = "Superuser" if self.is_superuser else f"Manager ({self.reportee_count} reportees)" if self.reportee_count > 0 else "Employee"
        user_info = QLabel(f"User: {self.current_user} | Role: {role_info}")
        user_info.setStyleSheet("font-weight: bold;")
        header_layout.addWidget(user_info)
        
        if not self.is_superuser and (self.score_chart_visible or self.reportee_count > 0):
            self.team_toggle = QCheckBox("View Team Data")
            self.team_toggle.toggled.connect(self.toggle_team_view)
            header_layout.addWidget(self.team_toggle)
        
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self.status_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.load_button = QPushButton("Refresh Data")
        self.load_button.clicked.connect(self.load_data)
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)
        
        # Main content
        splitter = QSplitter(Qt.Vertical)
        
        # Charts area (if visible)
        if self.score_chart_visible:
            self.tabs = QTabWidget()
            self.create_overall_tab()
            self.create_section_tab()
            self.create_question_tab()
            splitter.addWidget(self.tabs)
        
                # Feedback display area - Initialize these first
        feedback_container = QWidget()
        feedback_layout = QVBoxLayout()
        
        # General Feedback section - Now properly initialized
        general_feedback_group = QGroupBox("General Feedback")
        general_feedback_layout = QVBoxLayout()
        self.general_feedback_display = QTextEdit()
        self.general_feedback_display.setReadOnly(True)
        general_feedback_layout.addWidget(self.general_feedback_display)
        general_feedback_group.setLayout(general_feedback_layout)
        feedback_layout.addWidget(general_feedback_group)
        
        # Indirect Feedback section - Now properly initialized
        if self.reportee_count > 0 or self.is_superuser:
            indirect_feedback_group = QGroupBox("Indirect Feedback from Reportees")
            indirect_feedback_layout = QVBoxLayout()
            self.indirect_feedback_display = QTextEdit()
            self.indirect_feedback_display.setReadOnly(True)
            indirect_feedback_layout.addWidget(self.indirect_feedback_display)
            indirect_feedback_group.setLayout(indirect_feedback_layout)
            feedback_layout.addWidget(indirect_feedback_group)
        
        feedback_container.setLayout(feedback_layout)
        splitter.addWidget(feedback_container)

        # Set splitter sizes
        splitter.setSizes([600, 300] if self.score_chart_visible else [0, 900])
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
    
    def create_overall_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        self.overall_canvas = FigureCanvasQTAgg(plt.figure(figsize=(8, 6)))
        layout.addWidget(self.overall_canvas)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Overall")
    
    def create_section_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Section selector
        section_layout = QHBoxLayout()
        section_layout.addWidget(QLabel("Section:"))
        self.section_combo = QComboBox()
        self.section_combo.addItems(self.questions_df['Category'].unique())
        self.section_combo.currentTextChanged.connect(self.update_section_analysis)
        section_layout.addWidget(self.section_combo)
        section_layout.addStretch(1)
        layout.addLayout(section_layout)
        
        # Section canvas
        self.section_canvas = FigureCanvasQTAgg(plt.figure(figsize=(8, 6)))
        layout.addWidget(self.section_canvas)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "By Section")
    
    def create_question_tab(self):
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        container = QWidget()
        layout = QVBoxLayout()
        
        # Question selector
        question_layout = QHBoxLayout()
        question_layout.addWidget(QLabel("Section:"))
        self.question_section_combo = QComboBox()
        self.question_section_combo.addItems(self.questions_df['Category'].unique())
        self.question_section_combo.currentTextChanged.connect(self.update_question_list)
        question_layout.addWidget(self.question_section_combo)
        
        question_layout.addWidget(QLabel("Question:"))
        self.question_combo = QComboBox()
        self.question_combo.currentTextChanged.connect(self.update_question_analysis)
        question_layout.addWidget(self.question_combo)
        question_layout.addStretch(1)
        layout.addLayout(question_layout)
        
        # Question canvas
        self.question_canvas = FigureCanvasQTAgg(plt.figure(figsize=(8, 6)))
        layout.addWidget(self.question_canvas)
        container.setLayout(layout)
        tab.setWidget(container)
        self.tabs.addTab(tab, "By Question")
        
        self.update_question_list(self.question_section_combo.currentText())
    
    def update_question_list(self, category):
        self.question_combo.clear()
        questions = self.questions_df[self.questions_df['Category'] == category]
        for _, row in questions.iterrows():
            self.question_combo.addItem(row['Question'], row['QuestionID'])
    
    def toggle_team_view(self, checked):
        self.viewing_team_data = checked
        self.load_data()
        self.setWindowTitle(f"Survey Analysis - {self.current_user}'s Team" if checked else f"Survey Analysis - {self.current_user}")
    
    def load_data(self):
        conn = sqlite3.connect(DATABASE_NAME)
        try:
            # Get user ID
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username=?", (self.current_user,))
            user_id = cursor.fetchone()[0]
            
            # Base query
            query = """
            SELECT f.*, u.username 
            FROM feedback f
            JOIN users u ON f.user_id = u.id
            WHERE f.is_aggregated = 0
            """
            params = []
            
            if self.viewing_team_data and not self.is_superuser:
                # Get team members
                cursor.execute("SELECT username FROM users WHERE manager=?", (self.current_user,))
                team_members = [row[0] for row in cursor.fetchall()]
                if team_members:
                    query += " AND (u.username=? OR u.username IN ({seq}))".format(
                        seq=','.join(['?']*len(team_members)))
                    params = [self.current_user] + team_members
                else:
                    query += " AND u.username=?"
                    params = [self.current_user]
            elif not self.is_superuser and not self.viewing_team_data:
                query += " AND u.username=?"
                params = [self.current_user]
            
            # Load feedback data
            self.feedback_df = pd.read_sql_query(query, conn, params=params)
            
            # Load manager feedback if applicable
            if (not self.is_superuser and 
                self.reportee_count < MIN_REPORTEES_FOR_SCORECHART and
                not self.viewing_team_data and 
                self.manager_name):
                
                manager_query = """
                SELECT f.*, u.username 
                FROM feedback f
                JOIN users u ON f.user_id = u.id
                WHERE f.is_aggregated = 1 AND u.username = ? AND f.response_text LIKE ?
                """
                self.manager_feedback_df = pd.read_sql_query(
                    manager_query, 
                    conn, 
                    params=[self.manager_name, f"%{self.current_user}%"]
                )
            
            # Update displays
            if not self.feedback_df.empty or not self.manager_feedback_df.empty:
                self.update_analyses()
            else:
                self.show_no_data_message()
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
        finally:
            conn.close()
    
    # def show_no_data_message(self):
    #     if hasattr(self, 'overall_canvas'):
    #         self.overall_canvas.figure.clear()
    #         ax = self.overall_canvas.figure.add_subplot(111)
    #         ax.text(0.5, 0.5, "No feedback data available", ha='center', va='center')
    #         self.overall_canvas.draw()
        
    #     if hasattr(self, 'section_canvas'):
    #         self.section_canvas.figure.clear()
    #         self.section_canvas.draw()
        
    #     if hasattr(self, 'question_canvas'):
    #         self.question_canvas.figure.clear()
    #         self.question_canvas.draw()
        
    #     self.general_feedback_display.setPlainText("No general feedback available")
        
    #     if hasattr(self, 'indirect_feedback_display'):
    #         self.indirect_feedback_display.setPlainText("No indirect feedback available")
        
    #     self.status_label.setText("No feedback data found for current view")
    
    def show_no_data_message(self):
        """Safe version that checks for attribute existence"""
        try:
            if hasattr(self, 'overall_canvas'):
                self.overall_canvas.figure.clear()
                ax = self.overall_canvas.figure.add_subplot(111)
                ax.text(0.5, 0.5, "No feedback data available", ha='center', va='center')
                self.overall_canvas.draw()
            
            if hasattr(self, 'section_canvas'):
                self.section_canvas.figure.clear()
                self.section_canvas.draw()
            
            if hasattr(self, 'question_canvas'):
                self.question_canvas.figure.clear()
                self.question_canvas.draw()
            
            if hasattr(self, 'general_feedback_display'):
                self.general_feedback_display.setPlainText("No general feedback available")
            
            if hasattr(self, 'indirect_feedback_display'):
                self.indirect_feedback_display.setPlainText("No indirect feedback available")
            
            self.status_label.setText("No feedback data found for current view")
        except Exception as e:
            print(f"Error showing no data message: {e}")

    def update_analyses(self):
        if not hasattr(self, 'feedback_df') or self.feedback_df.empty:
            self.show_no_data_message()
            return
        
        try:
            # Update overall analysis
            if self.score_chart_visible:
                self.update_overall_analysis()
            
            # Update current section analysis
            if hasattr(self, 'section_combo'):
                self.update_section_analysis(self.section_combo.currentText())
            
            # Update current question analysis
            if hasattr(self, 'question_combo') and self.question_combo.count() > 0:
                self.update_question_analysis(self.question_combo.currentText())
            
            # Update feedback displays
            self.update_feedback_displays()
            
            # Special message for managers with few reportees
            if (not self.is_superuser and 
                self.reportee_count < MIN_REPORTEES_FOR_SCORECHART and
                not self.viewing_team_data):
                
                msg = ("Note: As you have fewer than 2 direct reportees, your individual feedback\n"
                      "has been included in your manager's analysis instead.")
                self.status_label.setText(msg)
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Analysis Error", f"Could not update analyses: {str(e)}")
    
    def update_feedback_displays(self):
        # General feedback
        general_feedback = self.feedback_df[self.feedback_df['feedback_type'] == 'General']
        if not general_feedback.empty:
            text = "\n\n".join(
                f"From {row['username']}:\n{row['response_text']}" 
                for _, row in general_feedback.iterrows()
            )
            self.general_feedback_display.setPlainText(text)
        else:
            self.general_feedback_display.setPlainText("No general feedback available")
        
        # Indirect feedback
        if hasattr(self, 'indirect_feedback_display'):
            indirect_feedback = self.feedback_df[self.feedback_df['feedback_type'] == 'Indirect']
            if not indirect_feedback.empty:
                text = "\n\n".join(
                    f"From {row['username']}:\n{row['response_text']}" 
                    for _, row in indirect_feedback.iterrows()
                )
                self.indirect_feedback_display.setPlainText(text)
            else:
                self.indirect_feedback_display.setPlainText("No indirect feedback available")
    
    # def update_overall_analysis(self):
    #     try:
    #         self.overall_canvas.figure.clear()
    #         ax = self.overall_canvas.figure.add_subplot(111)
            
    #         # Combine with manager feedback if applicable
    #         combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
    #         # Calculate average scores by category
    #         category_scores = combined_df.groupby('category')['response_value'].mean()
            
    #         colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
    #         bars = ax.bar(category_scores.index, category_scores.values, color=colors)
            
    #         title = f"{'Team' if self.viewing_team_data else 'My'} Overall Scores"
    #         if not self.manager_feedback_df.empty:
    #             title += " (Including manager's view)"
                
    #         ax.set_title(title)
    #         ax.set_ylabel('Average Score (1-4)')
    #         ax.set_ylim(0, 4)
    #         ax.grid(True, linestyle='--', alpha=0.7)
            
    #         for bar in bars:
    #             height = bar.get_height()
    #             ax.text(
    #                 bar.get_x() + bar.get_width() / 2., height + 0.1,
    #                 f'{height:.2f}', ha='center', va='bottom'
    #             )
            
    #         self.overall_canvas.figure.tight_layout()
    #         self.overall_canvas.draw()
    #     except Exception as e:
    #         self.show_no_data_message()
    #         QMessageBox.warning(self, "Error", f"Error updating overall analysis: {str(e)}")
    
    # def update_section_analysis(self, category):
    #     try:
    #         self.section_canvas.figure.clear()
    #         ax = self.section_canvas.figure.add_subplot(111)
            
    #         # Combine with manager feedback if applicable
    #         combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
    #         category_data = combined_df[combined_df['category'] == category]
            
    #         if category_data.empty:
    #             ax.text(0.5, 0.5, f"No data for {category} category", ha='center', va='center')
    #             self.section_canvas.draw()
    #             return
            
    #         question_scores = category_data.groupby(['question_id', 'question'])['response_value'].mean()
            
    #         questions = [q[1] for q in question_scores.index]
    #         shortened_questions = [q[:20] + '...' if len(q) > 20 else q for q in questions]
            
    #         colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
    #         bars = ax.bar(range(len(shortened_questions)), question_scores.values, color=colors)
            
    #         title = f"{category} Category - {'Team' if self.viewing_team_data else 'My'} Scores"
    #         if not self.manager_feedback_df.empty:
    #             title += " (Including manager's view)"
                
    #         ax.set_title(title)
    #         ax.set_ylabel('Average Score (1-4)')
    #         ax.set_ylim(0, 4)
    #         ax.set_xticks(range(len(shortened_questions)))
    #         ax.set_xticklabels(shortened_questions, rotation=45, ha='right')
    #         ax.grid(True, linestyle='--', alpha=0.7)
            
    #         self.section_canvas.figure.tight_layout()
    #         self.section_canvas.draw()
    #     except Exception as e:
    #         self.show_no_data_message()
    #         QMessageBox.warning(self, "Error", f"Error updating section analysis: {str(e)}")

    def update_overall_analysis(self):
        try:
            # Clear the previous figure
            self.overall_canvas.figure.clear()
            ax = self.overall_canvas.figure.add_subplot(111)
            
            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            # Filter only LM feedback with response values
            lm_feedback = combined_df[(combined_df['feedback_type'] == 'LM') & (combined_df['response_value'].notna())]
            
            if lm_feedback.empty:
                ax.text(0.5, 0.5, "No feedback data available", ha='center', va='center')
                self.overall_canvas.draw()
                return
            
            # Calculate average scores by category
            category_scores = lm_feedback.groupby('category')['response_value'].mean()
            
            if category_scores.empty:
                ax.text(0.5, 0.5, "No category scores available", ha='center', va='center')
                self.overall_canvas.draw()
                return
            
            # Create the bar chart
            colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
            bars = ax.bar(category_scores.index, category_scores.values, color=colors)
            
            # Set chart title and labels
            title = f"{'Team' if self.viewing_team_data else 'My'} Overall Scores"
            if not self.manager_feedback_df.empty:
                title += " (Including manager's view)"
                
            ax.set_title(title)
            ax.set_ylabel('Average Score (1-4)')
            ax.set_ylim(0, 4.5)
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom'
                )
            
            # Rotate x-axis labels if needed
            if len(category_scores) > 3:
                plt.setp(ax.get_xticklabels(), rotation=45, ha='right')
            
            self.overall_canvas.figure.tight_layout()
            self.overall_canvas.draw()
            
        except Exception as e:
            print(f"Error in update_overall_analysis: {e}")
            self.show_no_data_message()

    def update_section_analysis(self, category):
        try:
            # Clear the previous figure
            self.section_canvas.figure.clear()
            ax = self.section_canvas.figure.add_subplot(111)
            
            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            # Filter only LM feedback with response values for this category
            category_data = combined_df[
                (combined_df['category'].str.lower() == category.lower()) & 
                (combined_df['feedback_type'] == 'LM') & 
                (combined_df['response_value'].notna())
            ]
            
            if category_data.empty:
                ax.text(0.5, 0.5, f"No data for {category} category", ha='center', va='center')
                self.section_canvas.draw()
                return
            
            # Calculate average scores by question
            question_scores = category_data.groupby(['question_id', 'question'])['response_value'].mean()
            
            if question_scores.empty:
                ax.text(0.5, 0.5, f"No question scores for {category}", ha='center', va='center')
                self.section_canvas.draw()
                return
            
            # Prepare data for plotting
            questions = [q[1] for q in question_scores.index]  # Get full question text
            shortened_questions = [q[:40] + '...' if len(q) > 40 else q for q in questions]  # Shorten for display
            
            # Create the bar chart
            colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
            x_pos = np.arange(len(question_scores))
            bars = ax.bar(x_pos, question_scores.values, color=colors)
            
            # Set chart title and labels
            title = f"{category} Category - {'Team' if self.viewing_team_data else 'My'} Scores"
            if not self.manager_feedback_df.empty:
                title += " (Including manager's view)"
                
            ax.set_title(title)
            ax.set_ylabel('Average Score (1-4)')
            ax.set_ylim(0, 4.5)
            ax.set_xticks(x_pos)
            ax.set_xticklabels(shortened_questions, rotation=45, ha='right')
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                ax.text(
                    bar.get_x() + bar.get_width() / 2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom'
                )
            
            self.section_canvas.figure.tight_layout()
            self.section_canvas.draw()
            
        except Exception as e:
            print(f"Error in update_section_analysis: {e}")
            self.show_no_data_message()

    def update_question_analysis(self, question_text):
        if not question_text:
            return
            
        try:
            self.question_canvas.figure.clear()
            ax = self.question_canvas.figure.add_subplot(111)
            
            question_id = self.question_combo.currentData()
            
            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            question_data = combined_df[combined_df['question_id'] == question_id]
            
            if question_data.empty:
                ax.text(0.5, 0.5, "No data for this question", ha='center', va='center')
                self.question_canvas.draw()
                return
            
            option_counts = question_data['response_value'].value_counts().sort_index()
            
            # Get option texts
            question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
            option_labels = [question_row[f'Option{i}'] for i in range(1, 5)]
            
            # Ensure all options are represented
            all_options = pd.Series([0]*4, index=range(1, 5))
            for idx, count in option_counts.items():
                if idx in all_options.index:
                    all_options[idx] = count
            
            if all_options.sum() == 0:
                ax.text(0.5, 0.5, "No responses for this question", ha='center', va='center')
                self.question_canvas.draw()
                return
            
            # Create pie chart
            wedges, _ = ax.pie(
                all_options,
                labels=None,
                startangle=90,
                explode=[0.05]*4,
                shadow=True,
                colors=plt.cm.viridis(np.linspace(0.2, 0.8, 4)))
            
            title = f"{'Team' if self.viewing_team_data else 'My'} Responses: {question_text}"
            if not self.manager_feedback_df.empty:
                title += " (Including manager's view)"
            
            ax.set_title(title)
            ax.legend(wedges, option_labels, title="Options", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
            
            self.question_canvas.figure.tight_layout()
            self.question_canvas.draw()
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

class FeedbackApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.auth_window = AuthWindow(self.on_login_success)
        self.auth_window.show()
    
    def on_login_success(self, username, manager, is_superuser, reportee_count=0):
        self.auth_window.close()
        self.dashboard = Dashboard(username, manager, is_superuser, reportee_count)
        self.dashboard.show()
    
    def run(self):
        sys.exit(self.app.exec_())

class Dashboard(QWidget):
    def __init__(self, username, manager, is_superuser, reportee_count=0):
        super().__init__()
        self.username = username
        self.manager = manager
        self.is_superuser = is_superuser
        self.reportee_count = reportee_count
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Employee Feedback System - Dashboard')
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Welcome message
        welcome = QLabel(f'Welcome, {self.username}')
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet('font-size: 24px; font-weight: bold;')
        layout.addWidget(welcome)
        
        # User info
        role = 'Superuser' if self.is_superuser else f'Manager ({self.reportee_count} reportees)' if self.reportee_count > 0 else 'Employee'
        info = QLabel(
            f"Manager: {self.manager if self.manager else 'None'}\n"
            f"Role: {role}"
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Feedback Form Button
        feedback_btn = QPushButton('Feedback Form')
        feedback_btn.setFixedHeight(80)
        feedback_btn.clicked.connect(self.open_feedback_form)
        button_layout.addWidget(feedback_btn)
        
        # Score Chart Button
        self.score_btn = QPushButton('Score Chart')
        self.score_btn.setFixedHeight(80)
        self.score_btn.clicked.connect(self.open_score_chart)
        button_layout.addWidget(self.score_btn)
        
        # Disable score chart if not allowed
        if not self.is_superuser and self.reportee_count < MIN_REPORTEES_FOR_SCORECHART:
            self.score_btn.setEnabled(False)
            self.score_btn.setToolTip(
                f"Score chart requires {MIN_REPORTEES_FOR_SCORECHART} or more reportees. "
                f"You have {self.reportee_count}."
            )
        
        layout.addLayout(button_layout)
        
        # Manager-specific buttons
        if self.is_superuser or self.has_pending_approvals():
            layout.addWidget(QLabel('\nManager Actions:'))
            
            approval_btn = QPushButton('Review Pending Approvals')
            approval_btn.clicked.connect(self.show_approval_dialog)
            layout.addWidget(approval_btn)
        
        self.setLayout(layout)

    def has_pending_approvals(self):
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE manager=? AND is_approved=0",
            (self.username,)
        )
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0
    
    def show_approval_dialog(self):
        dialog = ApprovalDialog(self.username, self.is_superuser)
        dialog.exec_()
    
    def open_feedback_form(self):
        feedback_window = SurveyApp(self.username, self.manager)
        feedback_window.exec_()
    
    def open_score_chart(self):
        analysis_dialog = AnalysisApp(
            self.username, 
            self.manager, 
            self.is_superuser,
            self.reportee_count
        )
        analysis_dialog.exec_()

class ApprovalDialog(QDialog):
    def __init__(self, current_user, is_superuser=False):
        super().__init__()
        self.current_user = current_user
        self.is_superuser = is_superuser
        self.init_ui()
        self.load_pending_approvals()
        
    def init_ui(self):
        self.setWindowTitle('Pending Approvals')
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout()
        
        title = QLabel('Pending Registration Approvals')
        title.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title)
        
        # Table setup
        self.approval_table = QTableWidget()
        self.approval_table.setColumnCount(3)
        self.approval_table.setHorizontalHeaderLabels(['ID', 'Username', 'Manager'])
        self.approval_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.approval_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.approval_table)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.approve_btn = QPushButton('Approve Selected')
        self.approve_btn.clicked.connect(self.approve_selected)
        button_layout.addWidget(self.approve_btn)
        
        self.disapprove_btn = QPushButton('Disapprove Selected')
        self.disapprove_btn.clicked.connect(self.disapprove_selected)
        button_layout.addWidget(self.disapprove_btn)
        
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.close)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_pending_approvals(self):
        self.approval_table.setRowCount(0)
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        if self.is_superuser:
            cursor.execute(
                "SELECT id, username, manager FROM users WHERE is_approved=0"
            )
        else:
            cursor.execute(
                "SELECT id, username, manager FROM users WHERE manager=? AND is_approved=0",
                (self.current_user,)
            )
        
        approvals = cursor.fetchall()
        conn.close()
        
        if not approvals:
            self.approve_btn.setEnabled(False)
            self.disapprove_btn.setEnabled(False)
            self.approval_table.setRowCount(1)
            self.approval_table.setItem(0, 0, QTableWidgetItem("No pending approvals"))
            return
        
        self.approve_btn.setEnabled(True)
        self.disapprove_btn.setEnabled(True)
        
        for row, (user_id, username, manager) in enumerate(approvals):
            self.approval_table.insertRow(row)
            self.approval_table.setItem(row, 0, QTableWidgetItem(str(user_id)))
            self.approval_table.setItem(row, 1, QTableWidgetItem(username))
            self.approval_table.setItem(row, 2, QTableWidgetItem(manager))
    
    def approve_selected(self):
        selected = self.get_selected_ids()
        if not selected:
            QMessageBox.warning(self, 'Error', 'Please select at least one user')
            return
        
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        try:
            for user_id in selected:
                cursor.execute(
                    "UPDATE users SET is_approved=1 WHERE id=?",
                    (user_id,)
                )
            conn.commit()
            QMessageBox.information(self, 'Success', f'Approved {len(selected)} user(s)')
            self.load_pending_approvals()
        except Exception as e:
            conn.rollback()
            QMessageBox.critical(self, 'Error', f'Failed to approve users: {str(e)}')
        finally:
            conn.close()
    
    def disapprove_selected(self):
        selected = self.get_selected_ids()
        if not selected:
            QMessageBox.warning(self, 'Error', 'Please select at least one user')
            return
        
        reply = QMessageBox.question(
            self, 'Confirm Disapproval',
            f'Are you sure you want to disapprove {len(selected)} user(s)?\n\n'
            'This action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            conn = sqlite3.connect(DATABASE_NAME)
            cursor = conn.cursor()
            try:
                for user_id in selected:
                    cursor.execute(
                        "DELETE FROM users WHERE id=?",
                        (user_id,)
                    )
                conn.commit()
                QMessageBox.information(self, 'Success', f'Disapproved {len(selected)} user(s)')
                self.load_pending_approvals()
            except Exception as e:
                conn.rollback()
                QMessageBox.critical(self, 'Error', f'Failed to disapprove users: {str(e)}')
            finally:
                conn.close()
    
    def get_selected_ids(self):
        selected_ids = []
        for item in self.approval_table.selectedItems():
            if item.column() == 0:  # Only need one item per row
                selected_ids.append(int(item.text()))
        return list(set(selected_ids))  # Remove duplicates

if __name__ == '__main__':
    feedback_app = FeedbackApp()
    feedback_app.run()
