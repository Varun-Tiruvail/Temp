import sys
import os
import datetime
import pandas as pd
import sqlite3
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QWidget,
                            QRadioButton, QButtonGroup, QScrollArea,
                            QPushButton, QTextEdit, QMessageBox,
                            QGroupBox, QStackedWidget)
from PyQt5.QtCore import Qt

class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.setWindowTitle(f"Feedback Survey - {current_user}")
        self.resize(800, 600)
        
        # Initialize data
        self.questions_df = self.load_questions()
        self.lm_responses = {}
        
        # Create UI
        self.create_ui()
    
    def load_questions(self):
        """Load questions from Excel with validation"""
        try:
            df = pd.read_excel('survey_questions.xlsx')
            required_columns = ['QuestionID', 'Category', 'Question', 'Option1', 'Option2', 'Option3', 'Option4']
            if not all(col in df.columns for col in required_columns):
                raise ValueError("Missing required columns in questions file")
            return df
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load questions: {str(e)}")
            sys.exit(1)
    
    def create_ui(self):
        """Create the main UI components"""
        main_layout = QVBoxLayout()
        
        # Feedback type selector
        self.feedback_type_layout = QHBoxLayout()
        self.lm_feedback_btn = QPushButton("Manager Feedback")
        self.general_feedback_btn = QPushButton("General Feedback")
        
        self.lm_feedback_btn.setStyleSheet("font-weight: bold;")
        self.general_feedback_btn.setStyleSheet("font-weight: bold;")
        
        self.lm_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.general_feedback_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        
        self.feedback_type_layout.addWidget(self.lm_feedback_btn)
        self.feedback_type_layout.addWidget(self.general_feedback_btn)
        main_layout.addLayout(self.feedback_type_layout)
        
        # Stacked widget for different feedback types
        self.stacked_widget = QStackedWidget()
        self.create_lm_feedback_page()
        self.create_general_feedback_page()
        main_layout.addWidget(self.stacked_widget)
        
        # Submit button
        self.submit_button = QPushButton("Submit Feedback")
        self.submit_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.submit_button.clicked.connect(self.submit_feedback)
        main_layout.addWidget(self.submit_button)
        
        self.setLayout(main_layout)
    
    def create_lm_feedback_page(self):
        """Create the manager feedback page with questions"""
        page = QWidget()
        layout = QVBoxLayout()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout()
        
        # Organize questions by category
        categories = self.questions_df['Category'].unique()
        for category in categories:
            category_group = QGroupBox(category)
            category_layout = QVBoxLayout()
            
            # Add questions for this category
            for _, row in self.questions_df[self.questions_df['Category'] == category].iterrows():
                q_id = row['QuestionID']
                question_text = row['Question']
                
                question_group = QGroupBox(question_text)
                question_layout = QVBoxLayout()
                
                # Create radio buttons for options
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
                category_layout.addWidget(question_group)
            
            category_group.setLayout(category_layout)
            container_layout.addWidget(category_group)
        
        container.setLayout(container_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)
    
    def set_response(self, question_id, value):
        """Store the selected response for a question"""
        self.lm_responses[question_id] = value
    
    def create_general_feedback_page(self):
        """Create the general feedback page"""
        page = QWidget()
        layout = QVBoxLayout()
        
        label = QLabel("Please provide any general feedback or concerns:")
        layout.addWidget(label)
        
        self.general_feedback_input = QTextEdit()
        self.general_feedback_input.setPlaceholderText("Type your feedback here...")
        layout.addWidget(self.general_feedback_input)
        
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)
    
    def submit_feedback(self):
        """Handle submission of feedback to database"""
        # Create database filename with manager's name
        db_filename = f"Feedback_{self.manager_name}.db" if self.manager_name else "Feedback_General.db"
        
        try:
            with sqlite3.connect(db_filename) as conn:
                cursor = conn.cursor()
                
                # Create tables if they don't exist
                cursor.execute('''
                CREATE TABLE IF NOT EXISTS feedback_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    feedback_type TEXT,
                    question_id TEXT,
                    category TEXT,
                    response_value INTEGER,
                    response_text TEXT,
                    employee_name TEXT,
                    timestamp TEXT,
                    is_aggregated INTEGER DEFAULT 0
                )
                ''')
                
                current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Process manager feedback
                for q_id, response in self.lm_responses.items():
                    if response is not None:
                        question_data = self.questions_df[self.questions_df['QuestionID'] == q_id].iloc[0]
                        cursor.execute(
                            '''INSERT INTO feedback_responses 
                            (feedback_type, question_id, category, response_value, 
                             response_text, employee_name, timestamp)
                            VALUES (?, ?, ?, ?, ?, ?, ?)''',
                            ('LM', q_id, question_data['Category'], response,
                             question_data[f'Option{response}'], self.current_user, current_time)
                        )
                
                # Process general feedback
                general_feedback = self.general_feedback_input.toPlainText().strip()
                if general_feedback:
                    cursor.execute(
                        '''INSERT INTO feedback_responses 
                        (feedback_type, question_id, category, response_value,
                         response_text, employee_name, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        ('General', 'N/A', 'N/A', 0, general_feedback, self.current_user, current_time)
                    )
                
                # If user has a manager, create aggregated feedback entry
                if self.manager_name and self.manager_name.lower() != 'none':
                    cursor.execute(
                        '''INSERT INTO feedback_responses 
                        (feedback_type, question_id, category, response_value,
                         response_text, employee_name, timestamp, is_aggregated)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        ('Aggregate', 'N/A', 'N/A', 0, 
                         f"Feedback submission from {self.current_user}",
                         self.current_user, current_time, 1)
                    )
                
                conn.commit()
                
                QMessageBox.information(
                    self, "Success", 
                    "Feedback submitted successfully!\n"
                    f"Manager: {self.manager_name if self.manager_name else 'No manager assigned'}"
                )
                self.close()
                
        except Exception as e:
            QMessageBox.critical(
                self, "Error", 
                f"Failed to submit feedback: {str(e)}"
            )