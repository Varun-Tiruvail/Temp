# feedback_app.py - Full Updated Code
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

# ----------------- Database Classes -----------------
class FeedbackDatabase:
    def __init__(self):
        self.conn = sqlite3.connect('feedback.db')
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                encrypted_data TEXT NOT NULL,
                approved BOOLEAN NOT NULL DEFAULT 0
            )
        ''')
        # Feedback table (UPDATED)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback_responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee TEXT NOT NULL,
                manager TEXT NOT NULL,
                question_id TEXT,
                response INTEGER,
                general_feedback TEXT,
                approved BOOLEAN DEFAULT 0,
                hierarchy_level INTEGER NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(employee) REFERENCES users(username),
                FOREIGN KEY(manager) REFERENCES users(username)
            )
        ''')
        self.conn.commit()

    # ... (Keep existing user methods as-is until approve_users) ...

    def approve_users(self, usernames):
        cursor = self.conn.cursor()
        placeholders = ','.join(['?']*len(usernames))
        # Update user approval
        cursor.execute(f'''
            UPDATE users SET approved = 1 
            WHERE username IN ({placeholders})
        ''', usernames)
        
        # NEW: Update feedback approval
        cursor.execute(f'''
            UPDATE feedback_responses 
            SET approved = 1 
            WHERE employee IN ({placeholders})
        ''', usernames)
        
        self.conn.commit()

    # ... (Keep other methods as-is) ...

# ----------------- SurveyApp Class -----------------
class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.setWindowTitle(f"Feedback Survey Form - {current_user}")
        self.resize(800, 600)
        
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            return
            
        self.init_ui()

    def init_ui(self):
        # ... (Keep existing UI setup as-is until submit button) ...
        
        # Add submit button at bottom
        self.submit_btn = QPushButton("Submit Feedback")
        self.submit_btn.clicked.connect(self.submit_feedback)
        main_layout.addWidget(self.submit_btn)

    # NEW METHOD: Get management hierarchy
    def get_management_hierarchy(self):
        """Returns list of managers from direct to top-level"""
        hierarchy = []
        conn = sqlite3.connect('hierarchy.db')
        cursor = conn.cursor()
        
        current_user = self.current_user
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
            current_user = result[0]
            hierarchy.append(current_user)
        
        conn.close()
        return hierarchy

    # UPDATED SUBMIT METHOD
    def submit_feedback(self):
        conn = sqlite3.connect('feedback.db')
        cursor = conn.cursor()
        
        # Get all managers in hierarchy
        managers = self.get_management_hierarchy()
        if not managers:
            QMessageBox.warning(self, "Error", "No management hierarchy found!")
            return
            
        # Insert feedback for each level
        for level, manager in enumerate(managers, 1):
            # LM Feedback
            for q_id, response in self.lm_responses.items():
                if response is not None:
                    cursor.execute('''
                        INSERT INTO feedback_responses 
                        (employee, manager, question_id, response, hierarchy_level)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (self.current_user, manager, q_id, response, level))
            
            # General Feedback (only for direct manager)
            if level == 1:
                general_feedback = self.general_feedback_input.toPlainText()
                if general_feedback:
                    cursor.execute('''
                        INSERT INTO feedback_responses 
                        (employee, manager, general_feedback, hierarchy_level)
                        VALUES (?, ?, ?, ?)
                    ''', (self.current_user, manager, general_feedback, level))
        
        conn.commit()
        conn.close()
        QMessageBox.information(self, "Success", "Feedback submitted to hierarchy!")
        self.close()

# ----------------- Rest of the Code ----------------- 
# Keep ALL other classes and methods EXACTLY AS THEY WERE:
# - HierarchyValidator
# - RegistrationDialog
# - ApprovalDialog 
# - FeedbackLoginWindow
# - FeedbackMainWindow
# - Main execution block

# Only the above mentioned changes in FeedbackDatabase and SurveyApp classes are needed
# All other code remains identical to what you previously had