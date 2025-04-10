import sys
import os
import datetime
import pandas as pd
import sqlite3
from PyQt6.QtWidgets import (QApplication, QWidget, QTabWidget, QVBoxLayout, 
                             QLabel, QRadioButton, QButtonGroup, QScrollArea,
                             QPushButton, QLineEdit, QFormLayout, QMessageBox,
                             QGridLayout, QGroupBox)
from PyQt6.QtCore import Qt

class SurveyApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Feedback Survey Form")
        self.resize(800, 600)
        
        # Load questions from Excel
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            sys.exit(1)
            
        # User information
        self.user_info_layout = QFormLayout()
        self.name_input = QLineEdit()
        self.email_input = QLineEdit()
        self.dept_input = QLineEdit()
        
        self.user_info_layout.addRow("Name:", self.name_input)
        self.user_info_layout.addRow("Email:", self.email_input)
        self.user_info_layout.addRow("Department:", self.dept_input)
        
        # Create tabs
        self.tabs = QTabWidget()
        
        # Create sections (tabs)
        self.categories = ["Cultural", "Development", "Ways of Working"]
        self.responses = {}
        
        for category in self.categories:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            
            container = QWidget()
            layout = QVBoxLayout(container)
            
            # Filter questions for this category
            category_questions = self.questions_df[self.questions_df['Category'] == category]
            
            for _, row in category_questions.iterrows():
                q_id = row['QuestionID']
                question_text = row['Question']
                
                group_box = QGroupBox(question_text)
                group_layout = QVBoxLayout()
                
                # Create radio buttons for options
                option_group = QButtonGroup(self)
                self.responses[q_id] = None
                
                options = [row['Option1'], row['Option2'], row['Option3'], row['Option4']]
                option_values = [1, 2, 3, 4]  # Numeric values for options
                
                for i, (option, value) in enumerate(zip(options, option_values)):
                    radio = QRadioButton(option)
                    radio.setObjectName(f"{q_id}_{value}")
                    radio.toggled.connect(self.on_radio_toggled)
                    option_group.addButton(radio)
                    group_layout.addWidget(radio)
                
                group_box.setLayout(group_layout)
                layout.addWidget(group_box)
            
            scroll.setWidget(container)
            self.tabs.addTab(scroll, category)
        
        # Submit button
        self.submit_button = QPushButton("Submit Survey")
        self.submit_button.clicked.connect(self.submit_survey)
        
        # Main layout
        main_layout = QVBoxLayout()
        user_info_group = QGroupBox("User Information")
        user_info_group.setLayout(self.user_info_layout)
        
        main_layout.addWidget(user_info_group)
        main_layout.addWidget(self.tabs)
        main_layout.addWidget(self.submit_button)
        
        self.setLayout(main_layout)
    
    def on_radio_toggled(self):
        sender = self.sender()
        if sender.isChecked():
            q_id, value = sender.objectName().split('_')
            self.responses[q_id] = int(value)
    
    def submit_survey(self):
        # Validate user info
        name = self.name_input.text().strip()
        email = self.email_input.text().strip()
        dept = self.dept_input.text().strip()
        
        if not name or not email or not dept:
            QMessageBox.warning(self, "Missing Information", "Please fill in all user information fields.")
            return
        
        # Check if all questions have been answered
        unanswered = [q_id for q_id, resp in self.responses.items() if resp is None]
        
        if unanswered:
            msg = f"You have {len(unanswered)} unanswered questions. Do you want to continue?"
            reply = QMessageBox.question(self, "Incomplete Survey", msg,
                                         QMessageBox.StandardButton.Yes | 
                                         QMessageBox.StandardButton.No)
            
            if reply == QMessageBox.StandardButton.No:
                return
        
        # Create SQLite database with timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_filename = f"{name.replace(' ', '_')}_{timestamp}.db"
        
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()
        
        # Create tables
        cursor.execute('''
        CREATE TABLE user_info (
            name TEXT,
            email TEXT,
            department TEXT,
            timestamp TEXT
        )
        ''')
        
        cursor.execute('''
        CREATE TABLE responses (
            question_id TEXT,
            category TEXT,
            response INTEGER
        )
        ''')
        
        # Insert user info
        cursor.execute(
            "INSERT INTO user_info VALUES (?, ?, ?, ?)",
            (name, email, dept, timestamp)
        )
        
        # Insert responses
        for q_id, response in self.responses.items():
            # Get the category for this question
            q_row = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
            category = q_row['Category']
            
            cursor.execute(
                "INSERT INTO responses VALUES (?, ?, ?)",
                (q_id, category, response if response is not None else -1)
            )
        
        conn.commit()
        conn.close()
        
        QMessageBox.information(self, "Success", f"Survey submitted successfully!\nSaved to {db_filename}")
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SurveyApp()
    window.show()
    sys.exit(app.exec())