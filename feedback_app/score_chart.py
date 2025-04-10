import sys
import os
import glob
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                           QComboBox, QPushButton, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt
import matplotlib
from matplotlib import cm
matplotlib.use('Qt5Agg')

class ScoreChart(QDialog):
    def __init__(self, username, manager, is_superuser):
        super().__init__()
        self.username = username
        self.manager = manager
        self.is_superuser = is_superuser
        self.setWindowTitle('Feedback Score Analysis')
        self.resize(900, 700)
        
        # Load question definitions
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            sys.exit(1)
        
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Controls layout
        controls_layout = QHBoxLayout()
        
        # Add database selection for superusers/managers
        if self.is_superuser or self.manager:
            self.db_combo = QComboBox()
            self.db_combo.setFixedWidth(300)
            self.refresh_db_list()
            controls_layout.addWidget(QLabel("Select Database:"))
            controls_layout.addWidget(self.db_combo)
            
            refresh_btn = QPushButton("Refresh")
            refresh_btn.clicked.connect(self.refresh_db_list)
            controls_layout.addWidget(refresh_btn)
        
        controls_layout.addStretch()
        main_layout.addLayout(controls_layout)
        
        # Create matplotlib canvas
        self.canvas = FigureCanvasQTAgg(plt.Figure(figsize=(8, 6)))
        main_layout.addWidget(self.canvas)
        
        # Add help text
        help_label = QLabel("Hover over chart elements to see detailed information")
        help_label.setAlignment(Qt.AlignCenter)
        help_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(help_label)
        
        self.setLayout(main_layout)
        
        # Load and display data
        if self.is_superuser or self.manager:
            self.db_combo.currentTextChanged.connect(self.load_and_plot_data)
            if self.db_combo.count() > 0:
                self.load_and_plot_data(self.db_combo.currentText())
        else:
            # For regular employees, try to load their manager's data
            if self.manager:
                manager_db = f"{self.manager}.db"
                if os.path.exists(manager_db):
                    self.load_and_plot_data(manager_db)
                else:
                    QMessageBox.information(self, "No Data", "No feedback data available for your manager yet.")
            else:
                QMessageBox.information(self, "No Access", "Only managers and superusers can view score charts.")
    
    def refresh_db_list(self):
        """Refresh the list of available database files"""
        self.db_combo.clear()
        db_files = glob.glob("*.db")
        self.db_combo.addItems(db_files)
    
    def load_and_plot_data(self, db_file):
        """Load data from the selected database and plot it"""
        if not db_file:
            return
            
        try:
            conn = sqlite3.connect(db_file)
            
            # Load responses and merge with question data
            responses_df = pd.read_sql_query("SELECT * FROM Feedback", conn)
            merged_df = pd.merge(responses_df, self.questions_df, 
                               left_on='question_id', 
                               right_on='QuestionID', 
                               how='left')
            
            conn.close()
            
            # Filter only LM feedback with numeric responses
            lm_feedback = merged_df[(merged_df['feedback_type'] == 'LM') & 
                                   (merged_df['response'].str.isnumeric())]
            lm_feedback['response'] = lm_feedback['response'].astype(int)
            
            if lm_feedback.empty:
                self.show_message("No LM feedback data found in this database.")
                return
            
            # Calculate average scores by category
            category_scores = lm_feedback.groupby('category')['response'].mean()
            
            # Clear previous plot
            self.canvas.figure.clear()
            ax = self.canvas.figure.add_subplot(111)
            
            # Create bar chart
            colors = cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
            bars = ax.bar(category_scores.index, category_scores.values, color=colors)
            
            # Customize the plot
            ax.set_title(f'Feedback Scores - {os.path.splitext(db_file)[0]}', pad=20)
            ax.set_ylabel('Average Score (1-4)')
            ax.set_ylim(0, 4)
            ax.grid(True, linestyle='--', alpha=0.7)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                        f'{height:.2f}',
                        ha='center', va='bottom')
            
            self.canvas.draw()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load data: {str(e)}")
    
    def show_message(self, message):
        """Display a message on the canvas when no data is available"""
        self.canvas.figure.clear()
        ax = self.canvas.figure.add_subplot(111)
        ax.text(0.5, 0.5, message,
               horizontalalignment='center',
               verticalalignment='center',
               transform=ax.transAxes)
        ax.axis('off')
        self.canvas.draw()