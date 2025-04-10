import sys
import os
import datetime
import pandas as pd
import sqlite3
from PyQt5.QtWidgets import (QApplication, QWidget, QTabWidget, QVBoxLayout, QDialog,
                             QLabel, QRadioButton, QButtonGroup, QScrollArea,
                             QPushButton, QLineEdit, QFormLayout, QMessageBox,
                             QGridLayout, QGroupBox, QStackedWidget, QTextEdit, QHBoxLayout)
from PyQt5.QtCore import Qt

class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.setWindowTitle(f"Feedback Survey Form - {current_user}")
        self.resize(800, 600)
        
        # Load questions from Excel
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            sys.exit(1)
            
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Create feedback type buttons
        self.feedback_type_layout = QHBoxLayout()
        self.lm_feedback_btn = QPushButton("LM Feedback")
        self.general_feedback_btn = QPushButton("General Feedback")
        
        self.lm_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.general_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        
        self.feedback_type_layout.addWidget(self.lm_feedback_btn)
        self.feedback_type_layout.addWidget(self.general_feedback_btn)
        
        # Create stacked widget
        self.stacked_widget = QStackedWidget()
        
        # Page 1: LM Feedback (Tabbed interface)
        self.create_lm_feedback_page()
        
        # Page 2: General Feedback (Text input)
        self.create_general_feedback_page()
        
        # Add widgets to main layout
        main_layout.addLayout(self.feedback_type_layout)
        main_layout.addWidget(self.stacked_widget)
        
        # Submit button
        self.submit_button = QPushButton("Submit Feedback")
        self.submit_button.clicked.connect(self.submit_feedback)
        main_layout.addWidget(self.submit_button)
        
        self.setLayout(main_layout)
    
    def create_lm_feedback_page(self):
        """Create the tabbed LM feedback interface"""
        lm_page = QWidget()
        lm_layout = QVBoxLayout(lm_page)
        
        # Create tabs for LM feedback
        self.lm_tabs = QTabWidget()
        self.lm_responses = {}
        
        # Create sections (tabs)
        # self.categories = ["Cultural", "Development", "Ways of Working"]
        self.categories = self.questions_df['Category'].unique().tolist()
        
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
                self.lm_responses[q_id] = None
                
                options = [row['Option1'], row['Option2'], row['Option3'], row['Option4']]
                option_values = [1, 2, 3, 4]  # Numeric values for options
                
                for i, (option, value) in enumerate(zip(options, option_values)):
                    radio = QRadioButton(option)
                    radio.setObjectName(f"lm_{q_id}_{value}")
                    radio.toggled.connect(self.on_lm_radio_toggled)
                    option_group.addButton(radio)
                    group_layout.addWidget(radio)
                
                group_box.setLayout(group_layout)
                layout.addWidget(group_box)
            
            scroll.setWidget(container)
            self.lm_tabs.addTab(scroll, category)
        
        lm_layout.addWidget(self.lm_tabs)
        self.stacked_widget.addWidget(lm_page)
    
    def create_general_feedback_page(self):
        """Create the general feedback text input page"""
        general_page = QWidget()
        general_layout = QVBoxLayout(general_page)
        
        # General feedback label
        label = QLabel("Please provide any general feedback or concerns:")
        general_layout.addWidget(label)
        
        # Text edit for general feedback
        self.general_feedback_input = QTextEdit()
        self.general_feedback_input.setPlaceholderText("Type your feedback here...")
        general_layout.addWidget(self.general_feedback_input)
        
        self.stacked_widget.addWidget(general_page)
    
    def on_lm_radio_toggled(self):
        """Handle LM feedback radio button selections"""
        sender = self.sender()
        if sender.isChecked():
            _, q_id, value = sender.objectName().split('_')
            self.lm_responses[q_id] = int(value)
    
    def submit_feedback(self):
        """Handle submission of both LM and general feedback"""
        # Create database filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        db_filename = f"\\ScoreData\\{self.manager_name}_{timestamp}.db"
        
        # Connect to database
        conn = sqlite3.connect(db_filename)
        cursor = conn.cursor()
        
        # Create tables if they don't exist
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS Feedback (
            feedback_type TEXT,
            question_id TEXT,
            category TEXT,
            response TEXT,
            employee_name TEXT,
            timestamp TEXT
        )
        ''')
        
        # Get current timestamp
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Process LM Feedback if any questions were answered
        lm_feedback_exists = any(resp is not None for resp in self.lm_responses.values())
        if lm_feedback_exists:
            for q_id, response in self.lm_responses.items():
                if response is not None:
                    # Get the category for this question
                    q_row = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
                    category = q_row['Category']
                    question_text = q_row['Question']
                    option_text = q_row[f'Option{response}']
                    
                    cursor.execute(
                        "INSERT INTO Feedback VALUES (?, ?, ?, ?, ?, ?)",
                        ("LM", q_id, category, option_text, self.current_user, current_time)
                    )
        
        # Process General Feedback if any text was entered
        general_feedback = self.general_feedback_input.toPlainText().strip()
        if general_feedback:
            cursor.execute(
                "INSERT INTO Feedback VALUES (?, ?, ?, ?, ?, ?)",
                ("General", "N/A", "N/A", general_feedback, self.current_user, current_time)
            )
        
        # Commit changes and close connection
        conn.commit()
        conn.close()
        
        # Show success message
        if lm_feedback_exists or general_feedback:
            QMessageBox.information(
                self, 
                "Success", 
                f"Feedback submitted successfully!\nSaved to {db_filename}"
            )
            self.close()
        else:
            QMessageBox.warning(
                self,
                "No Feedback",
                "No feedback was provided. Please provide either LM or general feedback before submitting."
            )

# if __name__ == "__main__":
#     # For testing without the auth system
#     app = QApplication(sys.argv)
#     window = SurveyApp("TestUser", "TestManager")
#     window.show()
#     sys.exit(app.exec())