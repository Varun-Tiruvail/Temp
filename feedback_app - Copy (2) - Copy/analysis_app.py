import sys
import os
import glob
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QDialog,
                           QLabel, QComboBox, QTabWidget, QPushButton,
                           QFileDialog, QMessageBox, QScrollArea, QGroupBox, QStackedWidget,
                           QGridLayout, QSplitter, QCheckBox, QTextEdit)
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PyQt5.QtCore import Qt
import matplotlib
from matplotlib import cm
from PyQt5.QtGui import QFont
matplotlib.use('Qt5Agg')
from database import get_reportees, count_reportees
# Configuration - can be changed to adjust the threshold
MIN_REPORTEES_FOR_SCORECHART = 2  # Can be increased to 5 or more in future

def style_buttons(button):
    button.setStyleSheet("""
        QPushButton {
            background-color: #4CAF50;
            color: white;
            font-size: 14px;
            font-weight: bold;
            padding: 8px 16px;
            border-radius: 5px;
            border: 1px solid #388E3C;
        }
        QPushButton:hover {
            background-color: #45A049;
        }
        QPushButton:pressed {
            background-color: #388E3C;
        }
    """)

def beautify_charts(axes, title, xlabel=None, ylabel=None):
    axes.set_facecolor('#f9f9f9')
    axes.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)
    axes.set_title(title, fontsize=14, fontweight='bold', color='#333333')
    if xlabel:
        axes.set_xlabel(xlabel, fontsize=12, color='#333333')
    if ylabel:
        axes.set_ylabel(ylabel, fontsize=12, color='#333333')
    axes.tick_params(axis='both', which='major', labelsize=10, colors='#333333')

class MatplotlibCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.fig = fig
        
        self.annot = self.axes.annotate("", xy=(0,0), xytext=(20,20),
                                     textcoords="offset points",
                                     bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                     arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)
        
        self.fig.canvas.mpl_connect("motion_notify_event", self.hover)
        
    def hover(self, event):
        if not event.inaxes:
            return
        
        wedges = getattr(self, 'pie_wedges', None)
        labels = getattr(self, 'pie_labels', None)
        
        if not wedges or not labels:
            return
            
        for i, wedge in enumerate(wedges):
            if wedge.contains_point([event.x, event.y]):
                self.annot.set_visible(True)
                self.annot.set_text(labels[i])
                theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
                r = wedge.r/2
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                self.annot.xy = (x, y)
                self.draw_idle()
                return
                
        self.annot.set_visible(False)
        self.draw_idle()

class AnalysisApp(QDialog):
    def __init__(self, current_user, manager_name, is_superuser=False, reportee_count=0):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.is_superuser = is_superuser
        self.reportee_count = reportee_count

        self.setWindowTitle(f"Survey Analysis - {current_user}")
        self.resize(1200, 900)
        
        # Check if score chart should be visible
        self.score_chart_visible = (self.is_superuser or 
                                self.reportee_count >= MIN_REPORTEES_FOR_SCORECHART)
        
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
            # ... (rest of question loading code remains the same)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions file: {str(e)}")
            sys.exit(1)
            
        self.merged_data = None
        self.responses_df = None
        self.general_feedback_df = None
        
        main_layout = QVBoxLayout()
        
        # Simplified header with just user info
        header_layout = QHBoxLayout()
        role_info = "Superuser" if is_superuser else f"Manager ({reportee_count} reportees)"
        user_info = QLabel(f"User: {current_user} | Role: {role_info}")
        user_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(user_info)
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        # Controls area - just the refresh button
        controls_layout = QHBoxLayout()
        self.load_button = QPushButton("Refresh Data")
        style_buttons(self.load_button)
        self.load_button.clicked.connect(self.load_data)
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)
        
        # Create a splitter for main content
        splitter = QSplitter(Qt.Vertical)
        
        # Create tab widget for charts (only if score chart should be visible)
        if self.score_chart_visible:
            self.tabs = QTabWidget()
            self.create_overall_tab()
            self.create_section_tab()
            self.create_question_tab()
            splitter.addWidget(self.tabs)
        
        # Create feedback display area (unchanged)
        feedback_container = QWidget()
        feedback_layout = QVBoxLayout()
        general_feedback_group = QGroupBox("General Feedback")
        general_feedback_layout = QVBoxLayout()
        self.general_feedback_display = QTextEdit()
        self.general_feedback_display.setReadOnly(True)
        general_feedback_layout.addWidget(self.general_feedback_display)
        general_feedback_group.setLayout(general_feedback_layout)
        feedback_layout.addWidget(general_feedback_group)
        feedback_container.setLayout(feedback_layout)
        splitter.addWidget(feedback_container)
        
        # Set splitter sizes
        if self.score_chart_visible:
            splitter.setSizes([600, 300])
        else:
            splitter.setSizes([0, 900])
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
        
        # Automatically load data
        self.load_data()
    
    # def __init__(self, current_user, manager_name, is_superuser=False, reportee_count=0):
    #     super().__init__()
    #     self.current_user = current_user
    #     self.manager_name = manager_name
    #     self.is_superuser = is_superuser
    #     self.reportee_count = reportee_count
    #     self.viewing_team_data = False
    #     self.LessthanMin_data = False
    #     self.show_Reportees_data = False

    #     self.setWindowTitle(f"Survey Analysis - {current_user}")
    #     self.resize(1200, 900)  # Increased size for additional sections
        
    #     # Check if score chart should be visible
    #     self.score_chart_visible = (self.is_superuser or 
    #                               self.reportee_count >= MIN_REPORTEES_FOR_SCORECHART)
        
    #     try:
    #         self.questions_df = pd.read_excel('survey_questions.xlsx')
            
    #         required_columns = ['QuestionID', 'Category', 'Question', 
    #                           'Option1', 'Option2', 'Option3', 'Option4']
            
    #         column_alternatives = {
    #             'QuestionID': ['QuestionID', 'Question_ID', 'Id', 'ID'],
    #             'Category': ['Category', 'Section', 'Type'],
    #             'Question': ['Question', 'QuestionText', 'Text'],
    #             'Option1': ['Option1', 'Option_1', 'Choice1'],
    #             'Option2': ['Option2', 'Option_2', 'Choice2'],
    #             'Option3': ['Option3', 'Option_3', 'Choice3'],
    #             'Option4': ['Option4', 'Option_4', 'Choice4']
    #         }
            
    #         actual_columns = self.questions_df.columns.tolist()
    #         for expected, alternatives in column_alternatives.items():
    #             if expected not in actual_columns:
    #                 for alt in alternatives:
    #                     if alt in actual_columns:
    #                         self.questions_df.rename(columns={alt: expected}, inplace=True)
    #                         break
            
    #         missing_columns = [col for col in required_columns if col not in self.questions_df.columns]
    #         if missing_columns:
    #             raise KeyError(f"Missing required columns: {', '.join(missing_columns)}")
                
    #     except FileNotFoundError:
    #         QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
    #         sys.exit(1)
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Error loading questions file: {str(e)}")
    #         sys.exit(1)
            
    #     self.merged_data = None
    #     self.responses_df = None
    #     self.general_feedback_df = None
        
    #     main_layout = QVBoxLayout()
        
    #     # User info and view toggle
    #     header_layout = QHBoxLayout()
        
    #     role_info = "Superuser" if is_superuser else f"Manager ({reportee_count} reportees)"
    #     user_info = QLabel(f"User: {current_user} | Role: {role_info}")
    #     user_info.setStyleSheet("font-weight: bold; font-size: 14px;")
    #     header_layout.addWidget(user_info)
        
    #     # Only show team toggle if user has sufficient reportees or is superuser
    #     if (not is_superuser and manager_name and 
    #         (self.score_chart_visible or reportee_count > 0)):
    #         self.team_toggle = QCheckBox("View My Team's Data")
    #         self.team_toggle.setChecked(False)
    #         self.team_toggle.toggled.connect(self.toggle_team_view)
    #         header_layout.addWidget(self.team_toggle)

    #     ###############################

    #     self.show_Reportees_checkbox = QCheckBox("Only Reportees Data")
    #     self.show_Reportees_checkbox.setChecked(False)
    #     self.show_Reportees_checkbox.toggled.connect(self.handle_show_Reportees)
    #     header_layout.addWidget(self.show_Reportees_checkbox)

    #     ###############################

    #     self.MinPeers_checkbox = QCheckBox("Only Reportees Data With Less Than Min Peers")
    #     self.MinPeers_checkbox.setChecked(False)
    #     self.MinPeers_checkbox.toggled.connect(self.handle_MinPeers)
    #     header_layout.addWidget(self.MinPeers_checkbox)

    #     ###############################

    #     header_layout.addStretch(1)
    #     main_layout.addLayout(header_layout)
        
    #     # Controls area
    #     controls_layout = QHBoxLayout()
        
    #     self.load_button = QPushButton("Refresh Data")
    #     style_buttons(self.load_button)
    #     self.load_button.clicked.connect(self.load_data)
        
    #     controls_layout.addWidget(self.load_button)
    #     controls_layout.addStretch(1)
        
    #     # Create a splitter for main content
    #     splitter = QSplitter(Qt.Vertical)
        
    #     # Create tab widget for charts (only if score chart should be visible)
    #     if self.score_chart_visible:
    #         self.tabs = QTabWidget()
    #         self.create_overall_tab()
    #         self.create_section_tab()
    #         self.create_question_tab()
    #         splitter.addWidget(self.tabs)
        
    #     # Create feedback display area
    #     feedback_container = QWidget()
    #     feedback_layout = QVBoxLayout()
        
    #     # General Feedback section
    #     general_feedback_group = QGroupBox("General Feedback")
    #     general_feedback_layout = QVBoxLayout()
    #     self.general_feedback_display = QTextEdit()
    #     self.general_feedback_display.setReadOnly(True)
    #     general_feedback_layout.addWidget(self.general_feedback_display)
    #     general_feedback_group.setLayout(general_feedback_layout)
    #     feedback_layout.addWidget(general_feedback_group)
        
    #     feedback_container.setLayout(feedback_layout)
    #     splitter.addWidget(feedback_container)
        
    #     # Set splitter sizes (more space for charts if visible)
    #     if self.score_chart_visible:
    #         splitter.setSizes([600, 300])
    #     else:
    #         splitter.setSizes([0, 900])  # Show only feedback if no score chart
        
    #     main_layout.addLayout(controls_layout)
    #     main_layout.addWidget(splitter)
        
    #     self.setLayout(main_layout)
        
    #     # Automatically load data
    #     self.load_data()

    # def update_overall_analysis(self):
    #     if self.merged_data is None:
    #         return

    #     try:
    #         self.overall_canvas.axes.clear()

    #         # Always calculate your average from your own data only
    #         your_data = self.merged_data[self.merged_data['db_file'].str.contains(self.current_user)]
    #         your_avg = your_data.groupby('Category')['response_value'].mean().mean()
            
    #         # Always calculate team average from all data (excluding your own)
    #         team_data = self.merged_data[~self.merged_data['db_file'].str.contains(self.current_user)]
    #         team_avg = team_data.groupby('Category')['response_value'].mean().mean()

    #         # Prepare data for plotting
    #         labels = ['My Average', 'Team Average']
    #         values = [your_avg, team_avg]
    #         colors = ['#1f77b4', '#ff7f0e']  # Blue for you, orange for team

    #         # Create plot
    #         bars = self.overall_canvas.axes.bar(labels, values, color=colors)

    #         beautify_charts(self.overall_canvas.axes, 
    #                     "Overall Performance Comparison", 
    #                     ylabel='Average Score (1-4)')
    #         self.overall_canvas.axes.set_ylim(0, 4)

    #         # Add value labels on top of bars
    #         for bar in bars:
    #             height = bar.get_height()
    #             self.overall_canvas.axes.text(
    #                 bar.get_x() + bar.get_width() / 2., height + 0.1,
    #                 f'{height:.2f}', ha='center', va='bottom', fontsize=12, color='#333333'
    #             )

    #         # Highlight midpoint (2.5) more prominently
    #         midpoint = 2.5
    #         self.overall_canvas.axes.axhline(midpoint, color='red', linestyle='--', linewidth=2, alpha=0.7)
            
    #         # Add midpoint label at the top of the chart
    #         xlim = self.overall_canvas.axes.get_xlim()
    #         self.overall_canvas.axes.text(
    #             xlim[1] - 0.5, midpoint + 0.05, 
    #             f'Midpoint: {midpoint}', 
    #             color='red', ha='right', va='bottom',
    #             bbox=dict(facecolor='white', edgecolor='red', boxstyle='round,pad=0.5')
    #         )

    #         self.overall_canvas.fig.tight_layout()
    #         self.overall_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating overall analysis: {str(e)}")

    def handle_show_Reportees(self, checked):
        """Handle 'Show Reportees' checkbox state"""
        self.show_Reportees_data = checked
        self.load_data()
        self.update_window_title()

    def handle_MinPeers(self, checked):
        """Handle 'Data of only Less than Min Peers' checkbox state"""
        self.LessthanMin_data = checked
        self.load_data()
        self.update_window_title()

    # def toggle_team_view(self, checked):
    #     """Toggle between individual and team view"""
    #     self.viewing_team_data = checked
    #     self.load_data()
    #     self.update_window_title()
    def toggle_team_view(self, checked):
        """Toggle between individual and team view (affects only section/question tabs)"""
        self.viewing_team_data = checked
        self.update_window_title()
        
        # Refresh only section and question analyses (skip overall)
        if self.score_chart_visible:
            self.update_section_analysis(self.section_combo.currentText())
            self.update_question_analysis(self.question_combo.currentText())
    
    def update_window_title(self):
        """Update window title based on current view"""
        if self.viewing_team_data:
            self.setWindowTitle(f"Survey Analysis - {self.manager_name}'s Team")
        else:
            self.setWindowTitle(f"Survey Analysis - {self.current_user}")
    
    def get_score_data_path(self):
        """Get the path to the ScoreData folder, creating if needed"""
        score_data_path = os.path.join(os.path.dirname(__file__), "ScoreData")
        if not os.path.exists(score_data_path):
            try:
                os.makedirs(score_data_path)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not create ScoreData folder: {str(e)}")
                return None
        return score_data_path

    def load_data(self):
        """Load data from ScoreData folder (your data + team data for overall analysis)"""
        score_data_path = self.get_score_data_path()
        if not score_data_path:
            return

        try:
            # Always load YOUR data (regardless of checkbox states)
            your_files = glob.glob(os.path.join(score_data_path, f"{self.current_user}_*.db"))
            
            # Always load TEAM data (if manager/superuser, else empty)
            team_files = []
            if self.manager_name or self.is_superuser:
                reportees = get_reportees(self.current_user)
                for reportee in reportees:
                    team_files += glob.glob(os.path.join(score_data_path, f"{reportee}_*.db"))
            
            # Combine all files (your data + team data)
            db_files = your_files + team_files
            
            if not db_files:
                QMessageBox.information(self, "No Data", "No survey data files found.")
                return
            
            # Rest of the loading logic remains the same...
            all_responses = []
            all_general_feedback = []
            
            for file in db_files:
                try:
                    conn = sqlite3.connect(file)
                    responses_df = pd.read_sql_query("SELECT * FROM Feedback WHERE feedback_type = 'LM'", conn)
                    responses_df['db_file'] = os.path.basename(file)
                    all_responses.append(responses_df)
                    
                    general_df = pd.read_sql_query("SELECT * FROM Feedback WHERE feedback_type = 'General'", conn)
                    if not general_df.empty:
                        general_df['db_file'] = os.path.basename(file)
                        all_general_feedback.append(general_df)
                    
                    conn.close()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not load data from {file}: {str(e)}")
            
            # Process responses and feedback (same as before)
            if all_responses:
                self.responses_df = pd.concat(all_responses)
                self.responses_df['response_value'] = pd.to_numeric(self.responses_df['response'], errors='coerce')
                
                if self.responses_df['response_value'].isna().any():
                    option_mapping = {}
                    for _, row in self.questions_df.iterrows():
                        for i in range(1, 5):
                            option_mapping[row[f'Option{i}']] = i
                    self.responses_df['response_value'] = self.responses_df['response'].map(option_mapping)
                
                self.merged_data = pd.merge(
                    self.responses_df,
                    self.questions_df,
                    left_on='question_id',
                    right_on='QuestionID',
                    how='left'
                )
            
            if all_general_feedback:
                self.general_feedback_df = pd.concat(all_general_feedback)
                feedback_texts = self.general_feedback_df.groupby('employee_name')['response'].apply(
                    lambda x: "\n".join([f"- {text}" for text in x])
                )
                feedback_display = "\n\n".join([f"-\n {text}" for name, text in feedback_texts.items()])
                self.general_feedback_display.setPlainText(feedback_display)
            else:
                self.general_feedback_display.setPlainText("No general feedback available.")
            
            # Update analyses
            self.update_overall_analysis()  # Always updates (static)
            
            # Update section/question analyses based on checkbox states
            if self.score_chart_visible:
                self.update_section_analysis(self.section_combo.currentText())
                self.update_question_analysis(self.question_combo.currentText())
            
            QMessageBox.information(
                self, "Data Loaded", 
                f"Loaded data from {len(db_files)} files\n"
                f"Viewing: {'Team Data' if self.viewing_team_data else 'My Data'}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")

    # def load_data(self):
    #     """Load data from ScoreData folder based on current view"""
    #     score_data_path = self.get_score_data_path()
    #     if not score_data_path:
    #         return

    #     try:
    #         if self.viewing_team_data and not self.is_superuser:
    #             # Load all files for the manager's team
    #             db_files = glob.glob(os.path.join(score_data_path, f"{self.current_user}_*.db"))
    #             Reportees = get_reportees(self.current_user)
    #             for reportee in Reportees:
    #                 print(reportee)
    #                 db_files=db_files + glob.glob(os.path.join(score_data_path, f"{reportee}_*.db"))
    #             print(db_files)
            
    #         elif self.LessthanMin_data and not self.is_superuser:
    #             # Load only files for the current user's reportees
    #             # db_files = glob.glob(os.path.join(score_data_path, f"{self.current_user}_*.db"))
    #             try:
    #                 Reportees = get_reportees(self.current_user)
    #                 for reportee in Reportees:
    #                     if count_reportees(reportee) < MIN_REPORTEES_FOR_SCORECHART:
    #                         print(reportee)
    #                         db_files=db_files + glob.glob(os.path.join(score_data_path, f"{reportee}_*.db"))
    #                 print(db_files)
    #             except Exception as e:
    #                 # QMessageBox.warning(self, "Error", f"Reportees With Less Not Available: {str(e)}")
    #                 QMessageBox.warning(self, "Error", "Reportees With Less Than Minimum Reportees Not Available.")
    #                 return

    #         elif self.show_Reportees_data and not self.is_superuser:
    #             # Load only files for the current user's reportees
    #             # db_files = glob.glob(os.path.join(score_data_path, f"{self.current_user}_*.db"))
    #             try:
    #                 Reportees = get_reportees(self.current_user)
    #                 for reportee in Reportees:
    #                     print(reportee)
    #                     db_files=glob.glob(os.path.join(score_data_path, f"{reportee}_*.db"))
    #                 print(db_files)
    #             except Exception as e:
    #                 QMessageBox.warning(self, "Error", f"Could not load data for reportees: {str(e)}")
    #                 return

    #         elif self.is_superuser:
    #             # Superuser sees all files
    #             db_files = glob.glob(os.path.join(score_data_path, "*.db"))
    #         else:
    #             # Load only files for the current user
    #             db_files = glob.glob(os.path.join(score_data_path, f"{self.current_user}_*.db"))
    #             print(db_files)
                
    #         if not db_files:
    #             QMessageBox.information(self, "No Data", "No survey data files found.")
    #             return
            
    #         all_responses = []
    #         all_general_feedback = []
            
    #         for file in db_files:
    #             try:
    #                 conn = sqlite3.connect(file)
                    
    #                 # Load standard feedback
    #                 responses_df = pd.read_sql_query("SELECT * FROM Feedback WHERE feedback_type = 'LM'", conn)
    #                 responses_df['db_file'] = os.path.basename(file)
    #                 all_responses.append(responses_df)
                    
    #                 # Load general feedback
    #                 general_df = pd.read_sql_query(
    #                     "SELECT * FROM Feedback WHERE feedback_type = 'General'", 
    #                     conn
    #                 )
    #                 if not general_df.empty:
    #                     general_df['db_file'] = os.path.basename(file)
    #                     all_general_feedback.append(general_df)
                    
    #                 conn.close()
    #             except Exception as e:
    #                 QMessageBox.warning(self, "Error", f"Could not load data from {file}: {str(e)}")
            
    #         try:
    #             # Process standard feedback
    #             if all_responses:
    #                 self.responses_df = pd.concat(all_responses)
    #                 self.responses_df['response_value'] = pd.to_numeric(
    #                     self.responses_df['response'], 
    #                     errors='coerce'
    #                 )
                    
    #                 # For non-numeric responses, map them to numeric values
    #                 if self.responses_df['response_value'].isna().any():
    #                     option_mapping = {}
    #                     for _, row in self.questions_df.iterrows():
    #                         for i in range(1, 5):
    #                             option_text = row[f'Option{i}']
    #                             option_mapping[option_text] = i
                        
    #                     self.responses_df['response_value'] = self.responses_df['response'].map(option_mapping)
                    
    #                 # Merge with question definitions
    #                 self.merged_data = pd.merge(
    #                     self.responses_df,
    #                     self.questions_df,
    #                     left_on='question_id',
    #                     right_on='QuestionID',
    #                     how='left'
    #                 )
                
    #             # Process general feedback
    #             if all_general_feedback:
    #                 self.general_feedback_df = pd.concat(all_general_feedback)
    #                 feedback_texts = self.general_feedback_df.groupby('employee_name')['response'].apply(
    #                     lambda x: "\n".join([f"- {text}" for text in x])
    #                 )
    #                 feedback_display = "\n\n".join(
    #                     # [f"From {name}:\n{text}" for name, text in feedback_texts.items()]
    #                     [f"-\n {text}" for name, text in feedback_texts.items()]
    #                 )
    #                 self.general_feedback_display.setPlainText(feedback_display)
    #             else:
    #                 self.general_feedback_display.setPlainText("No general feedback available.")
                
    #             # Update analyses if score chart is visible
    #             if self.score_chart_visible:
    #                 self.update_overall_analysis()
    #                 self.update_section_analysis(self.section_combo.currentText())
    #                 self.update_question_analysis(self.question_combo.currentText())
                
    #             QMessageBox.information(
    #                 self, "Data Loaded", 
    #                 f"Loaded data from {len(db_files)} files\n"
    #                 f"Viewing: {'Team Data' if self.viewing_team_data else 'My Data'}"
    #             )
    #         except Exception as e:
    #             QMessageBox.critical(self, "Error", f"Error processing data: {str(e)}")
        
    #     except Exception as e:
    #         QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")

    def create_overall_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        self.overall_canvas = MatplotlibCanvas(width=8, height=6)
        layout.addWidget(self.overall_canvas)
        
        help_label = QLabel("Hover over chart elements to see detailed information")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Overall Analysis")
    
    def create_section_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        section_controls = QHBoxLayout()
        section_controls.addWidget(QLabel("Select Section:"))
        
        self.section_combo = QComboBox()
        # self.section_combo.addItems(["Cultural", "Development", "Ways of Working"])
        self.section_combo.addItems(self.questions_df['Category'].unique().tolist())
        # self.categories = self.questions_df['Category'].unique().tolist()
        ##########################
        self.categories = self.questions_df['Category'].unique().tolist()
        self.section_combo.currentTextChanged.connect(self.update_section_analysis)
        
        section_controls.addWidget(self.section_combo)
        section_controls.addStretch(1)
        
        self.section_canvas = MatplotlibCanvas(width=8, height=6)
        
        layout.addLayout(section_controls)
        layout.addWidget(self.section_canvas)
        
        help_label = QLabel("Hover over chart elements to see detailed information")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Section Analysis")
    
    def create_question_tab(self):
        tab = QScrollArea()
        tab.setWidgetResizable(True)
        
        container = QWidget()
        layout = QVBoxLayout()
        
        question_controls = QHBoxLayout()
        question_controls.addWidget(QLabel("Select Section:"))
        
        self.question_section_combo = QComboBox()
        self.question_section_combo.addItems(["Cultural", "Development", "Ways of Working"])
        self.question_section_combo.currentTextChanged.connect(self.update_question_list)
        
        question_controls.addWidget(self.question_section_combo)
        
        question_controls.addWidget(QLabel("Select Question:"))
        self.question_combo = QComboBox()
        question_controls.addWidget(self.question_combo)
        
        self.question_combo.currentTextChanged.connect(self.update_question_analysis)
        
        question_controls.addStretch(1)
        
        self.question_canvas = MatplotlibCanvas(width=8, height=6)
        
        layout.addLayout(question_controls)
        layout.addWidget(self.question_canvas)
        
        help_label = QLabel("Hover over pie slices to see option details")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)
        
        container.setLayout(layout)
        tab.setWidget(container)
        self.tabs.addTab(tab, "Question Analysis")
        
        self.update_question_list("Cultural")
    
    def update_question_list(self, category):
        self.question_combo.clear()
        
        category_questions = self.questions_df[self.questions_df['Category'] == category]
        for _, row in category_questions.iterrows():
            self.question_combo.addItem(row['Question'], row['QuestionID'])

    def update_overall_analysis(self):
        if self.merged_data is None:
            return

        try:
            self.overall_canvas.axes.clear()

            # Filter YOUR responses (files containing your username)
            your_data = self.merged_data[self.merged_data['db_file'].str.contains(self.current_user)]
            your_avg = your_data.groupby('Category')['response_value'].mean().mean()
            
            # Filter TEAM responses (files NOT containing your username)
            team_data = self.merged_data[~self.merged_data['db_file'].str.contains(self.current_user)]
            team_avg = team_data.groupby('Category')['response_value'].mean().mean()

            # Prepare data for plotting
            labels = ['My Average', 'Team Average']
            values = [your_avg, team_avg]
            colors = ['#1f77b4', '#ff7f0e']  # Blue for you, orange for team

            # Create plot
            bars = self.overall_canvas.axes.bar(labels, values, color=colors)

            beautify_charts(self.overall_canvas.axes, 
                        "Overall Performance Comparison", 
                        ylabel='Average Score (1-4)')
            self.overall_canvas.axes.set_ylim(0, 4)

            # Add value labels on top of bars
            for bar in bars:
                height = bar.get_height()
                self.overall_canvas.axes.text(
                    bar.get_x() + bar.get_width() / 2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=12, color='#333333'
                )

            # Highlight midpoint (2.5) at the top
            midpoint = 2.5
            self.overall_canvas.axes.axhline(midpoint, color='red', linestyle='--', linewidth=2, alpha=0.7)
            
            # Add midpoint label at the top right
            xlim = self.overall_canvas.axes.get_xlim()
            self.overall_canvas.axes.text(
                xlim[1] - 0.5, midpoint + 0.05, 
                f'Midpoint: {midpoint}', 
                color='red', ha='right', va='bottom',
                bbox=dict(facecolor='white', edgecolor='red', boxstyle='round,pad=0.5')
            )

            self.overall_canvas.fig.tight_layout()
            self.overall_canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error updating overall analysis: {str(e)}")

    # def update_section_analysis(self, category):
    #     if self.merged_data is None:
    #         return
        
    #     try:
    #         self.section_canvas.axes.clear()
            
    #         category_data = self.merged_data[self.merged_data['Category'] == category]
            
    #         if category_data.empty:
    #             self.section_canvas.axes.text(0.5, 0.5, f"No data for {category} category",
    #                                         ha='center', va='center')
    #             self.section_canvas.draw()
    #             return
            
    #         question_scores = category_data.groupby(['QuestionID', 'Question'])['response_value'].mean()
            
    #         # Calculate average of all questions in this section
    #         section_average = question_scores.mean()
            
    #         questions = [q[1] for q in question_scores.index]
    #         shortened_questions = [q[:20] + '...' if len(q) > 20 else q for q in questions]
            
    #         colors = cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
    #         bars = self.section_canvas.axes.bar(range(len(shortened_questions)), question_scores.values, color=colors)
    #         beautify_charts(self.section_canvas.axes, 
    #                     f"{category} Category - {'Team' if self.viewing_team_data else 'My'} Scores\nSection Average: {section_average:.2f}", 
    #                     ylabel='Average Score (1-4)')
            
    #         self.section_canvas.axes.set_ylim(0, 4)
    #         self.section_canvas.axes.set_xticks(range(len(shortened_questions)))
    #         self.section_canvas.axes.set_xticklabels(shortened_questions, rotation=45, ha='right')
            
    #         self.section_canvas.bar_labels = questions
    #         self.section_canvas.bars = bars
            
    #         self.section_canvas.annot = self.section_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
    #                             textcoords="offset points",
    #                             bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                             arrowprops=dict(arrowstyle="->"))
    #         self.section_canvas.annot.set_visible(False)
            
    #         def hover(event):
    #             if not event.inaxes:
    #                 return

    #             for i, bar in enumerate(bars):
    #                 if bar.contains_point([event.x, event.y]):
    #                     self.section_canvas.annot.set_visible(True)
    #                     self.section_canvas.annot.set_text(f"{questions[i]}\nScore: {question_scores.values[i]:.2f}")
    #                     self.section_canvas.annot.xy = (bar.get_x() + bar.get_width() / 2, bar.get_height())
    #                     self.section_canvas.draw_idle()
    #                     return

    #             self.section_canvas.annot.set_visible(False)
    #             self.section_canvas.draw_idle()
            
    #         self.section_canvas.hover = hover
    #         self.section_canvas.fig.canvas.mpl_connect("motion_notify_event", self.section_canvas.hover)
            
    #         self.section_canvas.fig.tight_layout()
    #         self.section_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating section analysis: {str(e)}")

    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         question_id = self.question_combo.currentData()
    #         self.question_canvas.axes.clear()
            
    #         question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
            
    #         if question_data.empty:
    #             self.question_canvas.axes.text(0.5, 0.5, "No data for this question",
    #                                          ha='center', va='center')
    #             self.question_canvas.draw()
    #             return
            
    #         option_counts = question_data['response_value'].value_counts().sort_index()
            
    #         option_labels = []
    #         for i in range(1, 5):
    #             col_name = f'Option{i}'
    #             option_text = question_data[col_name].iloc[0] if not question_data.empty else f"Option {i}"
    #             option_labels.append(f"{i}: {option_text}")
            
    #         all_options = pd.Series([0, 0, 0, 0], index=[1, 2, 3, 4])
    #         for idx, count in option_counts.items():
    #             if idx > 0 and idx <= 4:
    #                 all_options[idx] = count
            
    #         if all_options.sum() == 0:
    #             self.question_canvas.axes.text(0.5, 0.5, "No responses for this question",
    #                                          ha='center', va='center')
    #             self.question_canvas.draw()
    #         else:
    #             wedges, _ = self.question_canvas.axes.pie(
    #                 all_options, 
    #                 labels=None,
    #                 autopct=None,
    #                 startangle=90,
    #                 explode=[0.05, 0.05, 0.05, 0.05],
    #                 shadow=True,
    #                 wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #                 colors=cm.viridis(np.linspace(0.2, 0.8, 4))
    #             )
                
    #             self.question_canvas.pie_wedges = wedges
                
    #             total = all_options.sum()
    #             detailed_labels = []
    #             for i, (label, count) in enumerate(zip(option_labels, all_options)):
    #                 percentage = (count / total) * 100 if total > 0 else 0
    #                 detailed_labels.append(f"{label}\nCount: {count}\n({percentage:.1f}%)")
                
    #             self.question_canvas.pie_labels = detailed_labels
                
    #             self.question_canvas.axes.set_title(
    #                 f"{'Team' if self.viewing_team_data else 'My'} Responses: {question_text}"
    #             )
    #             self.question_canvas.axes.legend(wedges, option_labels, title="Options", 
    #                                            loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
    #             self.question_canvas.axes.axis('equal')
                
    #             self.question_canvas.annot = self.question_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
    #                                        textcoords="offset points",
    #                                        bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                                        arrowprops=dict(arrowstyle="->"))
    #             self.question_canvas.annot.set_visible(False)
                
    #             self.question_canvas.fig.tight_layout()
                
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    def update_section_analysis(self, category):
        if self.merged_data is None:
            return
        
        try:
            self.section_canvas.axes.clear()
            
            # Split data into direct (you) and indirect (team)
            your_data = self.merged_data[self.merged_data['db_file'].str.contains(self.current_user)]
            team_data = self.merged_data[~self.merged_data['db_file'].str.contains(self.current_user)]
            
            # Get your scores
            your_scores = your_data[your_data['Category'] == category].groupby(
                ['QuestionID', 'Question'])['response_value'].mean()
            
            # Get team scores
            team_scores = team_data[team_data['Category'] == category].groupby(
                ['QuestionID', 'Question'])['response_value'].mean()
            
            # Align scores
            questions = list(set(your_scores.index.tolist() + team_scores.index.tolist()))
            questions.sort()  # Sort by QuestionID
            
            # Calculate averages
            your_avg = your_scores.mean() if not your_scores.empty else 0
            team_avg = team_scores.mean() if not team_scores.empty else 0
            
            # Plot setup
            width = 0.35
            x = np.arange(len(questions))
            
            # Plot bars
            your_bars = []
            team_bars = []
            question_labels = []
            
            for i, (qid, qtext) in enumerate(questions):
                your_val = your_scores.get((qid, qtext), 0)
                team_val = team_scores.get((qid, qtext), 0)
                
                your_bars.append(self.section_canvas.axes.bar(
                    x[i] - width/2, your_val, width, color='#1f77b4'))
                team_bars.append(self.section_canvas.axes.bar(
                    x[i] + width/2, team_val, width, color='#ff7f0e'))
                
                question_labels.append(qtext[:20] + '...' if len(qtext) > 20 else qtext)
            
            beautify_charts(self.section_canvas.axes,
                        f"{category} Category\nDirect Avg: {your_avg:.2f}, Indirect Avg: {team_avg:.2f}",
                        ylabel='Average Score (1-4)')
            
            self.section_canvas.axes.set_xticks(x)
            self.section_canvas.axes.set_xticklabels(question_labels, rotation=45, ha='right')
            self.section_canvas.axes.legend(['Direct (You)', 'Indirect (Team)'], loc='upper right')
            
            # Add hover functionality for both bar types
            self.section_canvas.bar_data = {
                'your': {'bars': your_bars, 'scores': your_scores},
                'team': {'bars': team_bars, 'scores': team_scores}
            }
            
            self.section_canvas.fig.tight_layout()
            self.section_canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error updating section analysis: {str(e)}")

    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         self.question_canvas.axes.clear()
    #         question_id = self.question_combo.currentData()
            
    #         # Split data into direct (you) and indirect (team)
    #         your_data = self.merged_data[
    #             (self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
    #         team_data = self.merged_data[
    #             (~self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
            
    #         # Create subplots for side-by-side pie charts
    #         self.question_canvas.fig.clf()
    #         ax1 = self.question_canvas.fig.add_subplot(121)
    #         ax2 = self.question_canvas.fig.add_subplot(122)
            
    #         # Plot your pie chart
    #         self.plot_pie_chart(ax1, your_data, "Your Responses")
    #         # Plot team pie chart
    #         self.plot_pie_chart(ax2, team_data, "Team Responses")
            
    #         # Add common legend
    #         handles, labels = ax1.get_legend_handles_labels()
    #         self.question_canvas.fig.legend(handles, labels, 
    #                                     title="Options",
    #                                     loc='lower center',
    #                                     ncol=4,
    #                                     bbox_to_anchor=(0.5, -0.05))
            
    #         self.question_canvas.fig.suptitle(
    #             f"Question Analysis: {question_text}", 
    #             y=1.02,
    #             fontsize=14,
    #             fontweight='bold'
    #         )
    #         self.question_canvas.fig.tight_layout()
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    # def plot_pie_chart(self, ax, data, title):
    #     """Helper function to plot individual pie charts"""
    #     option_counts = data['response_value'].value_counts().sort_index()
    #     all_options = pd.Series([0]*4, index=[1,2,3,4])
        
    #     for idx, count in option_counts.items():
    #         if 1 <= idx <= 4:
    #             all_options[idx] = count
        
    #     # Get option labels from questions_df
    #     question_row = self.questions_df[self.questions_df['QuestionID'] == data['QuestionID'].iloc[0]]
    #     option_labels = [question_row[f'Option{i}'].values[0] for i in range(1,5)]
        
    #     wedges, _, autotexts = ax.pie(
    #         all_options,
    #         labels=None,
    #         autopct='%1.1f%%',
    #         startangle=90,
    #         colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
    #         wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #         textprops={'color': 'white', 'fontweight': 'bold'}
    #     )
        
    #     # Beautify
    #     ax.set_title(title, fontsize=12, fontweight='bold')
    #     ax.axis('equal')
        
    #     # Store hover data
    #     ax.wedges = wedges
    #     ax.labels = [f"{i+1}: {option_labels[i]}" for i in range(4)]
        
    #     # Connect hover event
    #     self.question_canvas.mpl_connect("motion_notify_event", 
    #                                 lambda event: self.pie_hover(event, ax))

    # def pie_hover(self, event, ax):
    #     """Custom hover function for pie charts"""
    #     if not event.inaxes == ax:
    #         ax.annot.set_visible(False)
    #         self.question_canvas.draw_idle()
    #         return
        
    #     # Convert event coordinates to data space
    #     for wedge in ax.wedges:
    #         if wedge.contains_point((event.x, event.y)):
    #             ax.annot.set_visible(True)
    #             ax.annot.set_text(ax.labels[ax.wedges.index(wedge)])
    #             theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
    #             r = wedge.r/2
    #             x = r * np.cos(theta)
    #             y = r * np.sin(theta)
    #             ax.annot.xy = (x, y)
    #             self.question_canvas.draw_idle()
    #             return
        
    #     ax.anno.set_visible(False)
    #     self.question_canvas.draw_idle()

    # def plot_pie_chart(self, ax, data, title):
    #     """Helper function to plot individual pie charts"""
    #     # Initialize annotation for this axis
    #     ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
    #                         textcoords="offset points",
    #                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                         arrowprops=dict(arrowstyle="->"))
    #     ax.annot.set_visible(False)

    #     option_counts = data['response_value'].value_counts().sort_index()
    #     all_options = pd.Series([0]*4, index=[1,2,3,4])
        
    #     for idx, count in option_counts.items():
    #         if 1 <= idx <= 4:
    #             all_options[idx] = count
        
    #     # Get option labels from questions_df
    #     question_row = self.questions_df[self.questions_df['QuestionID'] == data['QuestionID'].iloc[0]]
    #     option_labels = [question_row[f'Option{i}'].values[0] for i in range(1,5)]
        
    #     wedges, _, autotexts = ax.pie(
    #         all_options,
    #         labels=None,
    #         autopct='%1.1f%%',
    #         startangle=90,
    #         colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
    #         wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #         textprops={'color': 'white', 'fontweight': 'bold'}
    #     )
        
    #     # Store references
    #     ax.wedges = wedges
    #     ax.labels = [f"{i+1}: {option_labels[i]}" for i in range(4)]
    #     ax.set_title(title, fontsize=12, fontweight='bold')
    #     ax.axis('equal')

    # def pie_hover(self, event, ax):
    #     """Custom hover function for pie charts"""
    #     if not event.inaxes == ax:
    #         ax.annot.set_visible(False)
    #         self.question_canvas.draw_idle()
    #         return
        
    #     # Convert event coordinates to data space
    #     for wedge in ax.wedges:
    #         if wedge.contains_point((event.x, event.y)):
    #             ax.annot.set_visible(True)
    #             ax.annot.set_text(ax.labels[ax.wedges.index(wedge)])
    #             theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
    #             r = wedge.r/2
    #             x = r * np.cos(theta)
    #             y = r * np.sin(theta)
    #             ax.annot.xy = (x, y)
    #             self.question_canvas.draw_idle()
    #             return
        
    #     ax.annot.set_visible(False)
    #     self.question_canvas.draw_idle()
    
    # def plot_pie_chart(self, ax, data, title):
    #     """Helper function to plot individual pie charts"""
    #     # Initialize annotation for this axis
    #     ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
    #                         textcoords="offset points",
    #                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                         arrowprops=dict(arrowstyle="->"))
    #     ax.annot.set_visible(False)

    #     option_counts = data['response_value'].value_counts().sort_index()
    #     all_options = pd.Series([0]*4, index=[1,2,3,4])
        
    #     for idx, count in option_counts.items():
    #         if 1 <= idx <= 4:
    #             all_options[idx] = count
        
    #     # Get option labels from questions_df
    #     question_row = self.questions_df[self.questions_df['QuestionID'] == data['QuestionID'].iloc[0]]
    #     option_labels = [f"{i+1}: {question_row[f'Option{i+1}'].values[0]}" for i in range(4)]
        
    #     wedges, texts, autotexts = ax.pie(
    #         all_options,
    #         labels=None,
    #         autopct='%1.1f%%',
    #         startangle=90,
    #         colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
    #         wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #         textprops={'color': 'black', 'fontsize': 9}  # Changed to visible text color
    #     )
        
    #     # Store references
    #     ax.wedges = wedges
    #     ax.labels = option_labels  # Store full labels for legend
    #     ax.set_title(title, fontsize=12, fontweight='bold')
    #     ax.axis('equal')

    #     return wedges  # Return wedges for legend creation

    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         self.question_canvas.fig.clf()
    #         ax1 = self.question_canvas.fig.add_subplot(121)
    #         ax2 = self.question_canvas.fig.add_subplot(122)

    #         # Plot charts and get wedges
    #         wedges1 = self.plot_pie_chart(ax1, your_data, "Your Responses")
    #         wedges2 = self.plot_pie_chart(ax2, team_data, "Team Responses")

    #         # Create unified legend using first plot's wedges
    #         handles = wedges1
    #         labels = [self.questions_df[self.questions_df['QuestionID'] == question_id]
    #                 [f'Option{i+1}'].values[0] for i in range(4)]

    #         # Add legend below both charts
    #         self.question_canvas.fig.legend(
    #             handles, labels,
    #             title="Response Options:",
    #             loc='lower center',
    #             ncol=2,
    #             bbox_to_anchor=(0.5, -0.1),
    #             fontsize=9
    #         )

    #         # Adjust layout
    #         self.question_canvas.fig.subplots_adjust(bottom=0.3, wspace=0.4)
    #         self.question_canvas.fig.suptitle(
    #             f"Question Analysis: {question_text}", 
    #             y=1.02,
    #             fontsize=14,
    #             fontweight='bold'
    #         )
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         question_id = self.question_combo.currentData()
            
    #         # Split data into direct (you) and indirect (team)
    #         your_data = self.merged_data[
    #             (self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
    #         team_data = self.merged_data[
    #             (~self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
            
    #         # Create subplots for side-by-side pie charts
    #         self.question_canvas.fig.clf()
    #         ax1 = self.question_canvas.fig.add_subplot(121)
    #         ax2 = self.question_canvas.fig.add_subplot(122)
            
    #         # Plot your pie chart
    #         wedges1 = self.plot_pie_chart(ax1, your_data, "Your Responses")
    #         # Plot team pie chart
    #         wedges2 = self.plot_pie_chart(ax2, team_data, "Team Responses")
            
    #         # Get option labels from questions_df
    #         question_row = self.questions_df[self.questions_df['QuestionID'] == question_id]
    #         labels = [question_row[f'Option{i+1}'].values[0] for i in range(4)]
            
    #         # Add common legend
    #         self.question_canvas.fig.legend(wedges1, labels, 
    #                                     title="Options",
    #                                     loc='lower center',
    #                                     ncol=2,
    #                                     bbox_to_anchor=(0.5, -0.1))
            
    #         self.question_canvas.fig.suptitle(
    #             f"Question Analysis: {question_text}", 
    #             y=1.02,
    #             fontsize=14,
    #             fontweight='bold'
    #         )
    #         self.question_canvas.fig.tight_layout()
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         question_id = self.question_combo.currentData()
            
    #         # Split data into direct (you) and indirect (team)
    #         your_data = self.merged_data[
    #             (self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
    #         team_data = self.merged_data[
    #             (~self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
            
    #         # Create subplots with adjusted spacing
    #         self.question_canvas.fig.clf()
    #         self.question_canvas.fig.subplots_adjust(right=0.7)  # Make space for legend
    #         ax1 = self.question_canvas.fig.add_subplot(121)
    #         ax2 = self.question_canvas.fig.add_subplot(122)
            
    #         # Plot charts and get counts
    #         wedges1, your_counts = self.plot_pie_chart(ax1, your_data, "Your Responses")
    #         wedges2, team_counts = self.plot_pie_chart(ax2, team_data, "Team Responses")
            
    #         # Get option labels
    #         question_row = self.questions_df[self.questions_df['QuestionID'] == question_id]
    #         labels = [f"{i+1}. {question_row[f'Option{i+1}'].values[0]}" for i in range(4)]
            
    #         # Add unified legend on the right
    #         self.question_canvas.fig.legend(
    #             wedges1, labels,
    #             title="Response Options",
    #             loc='center right',
    #             bbox_to_anchor=(1.25, 0.5),
    #             fontsize=9
    #         )
            
    #         # Add main title
    #         self.question_canvas.fig.suptitle(
    #             f"Question Analysis: {question_text}",
    #             y=0.95,
    #             fontsize=14,
    #             fontweight='bold'
    #         )
            
    #         # Store counts for hover
    #         self.your_counts = your_counts
    #         self.team_counts = team_counts
            
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    # def plot_pie_chart(self, ax, data, title):
    #     """Helper function to plot pie charts and return counts"""
    #     # Initialize annotation
    #     ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
    #                         textcoords="offset points",
    #                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                         arrowprops=dict(arrowstyle="->"))
    #     ax.annot.set_visible(False)
        
    #     # Get counts
    #     option_counts = data['response_value'].value_counts().sort_index()
    #     all_options = pd.Series([0]*4, index=[1,2,3,4])
    #     for idx, count in option_counts.items():
    #         if 1 <= idx <= 4:
    #             all_options[idx] = count
        
    #     # Plot pie chart
    #     wedges, texts, autotexts = ax.pie(
    #         all_options,
    #         labels=None,
    #         autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
    #         startangle=90,
    #         colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
    #         wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #         textprops={'color': 'black', 'fontsize': 8}
    #     )
        
    #     # Store references
    #     ax.wedges = wedges
    #     ax.set_title(title, fontsize=11, pad=10)
    #     ax.axis('equal')
        
    #     return wedges, all_options

    # def pie_hover(self, event, ax):
    #     """Custom hover function showing counts"""
    #     if not event.inaxes == ax:
    #         ax.annot.set_visible(False)
    #         self.question_canvas.draw_idle()
    #         return
        
    #     for i, wedge in enumerate(ax.wedges):
    #         if wedge.contains_point((event.x, event.y)):
    #             count = self.your_counts[i+1] if ax.get_title() == "Your Responses" else self.team_counts[i+1]
    #             ax.annot.set_visible(True)
    #             ax.annot.set_text(f"Count: {count}")
    #             theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
    #             r = wedge.r/2
    #             x = r * np.cos(theta)
    #             y = r * np.sin(theta)
    #             ax.annot.xy = (x, y)
    #             self.question_canvas.draw_idle()
    #             return
        
    #     ax.annot.set_visible(False)
    #     self.question_canvas.draw_idle()



    # def update_question_analysis(self, question_text):
    #     if self.merged_data is None or not question_text:
    #         return
        
    #     try:
    #         question_id = self.question_combo.currentData()
            
    #         # Split data into direct (you) and indirect (team)
    #         your_data = self.merged_data[
    #             (self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
    #         team_data = self.merged_data[
    #             (~self.merged_data['db_file'].str.contains(self.current_user)) &
    #             (self.merged_data['QuestionID'] == question_id)
    #         ]
            
    #         # Create figure with adjusted layout
    #         self.question_canvas.fig.clf()
            
    #         # Create gridspec for better layout control
    #         gs = self.question_canvas.fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[4, 1])
    #         ax1 = self.question_canvas.fig.add_subplot(gs[0, 0])
    #         ax2 = self.question_canvas.fig.add_subplot(gs[0, 1])
    #         legend_ax = self.question_canvas.fig.add_subplot(gs[1, :])
    #         legend_ax.axis('off')
            
    #         # Plot pie charts
    #         wedges1, your_counts = self.plot_pie_chart(ax1, your_data, "Your Responses")
    #         wedges2, team_counts = self.plot_pie_chart(ax2, team_data, "Team Responses")
            
    #         # Get option labels
    #         question_row = self.questions_df[self.questions_df['QuestionID'] == question_id]
    #         labels = [f"{i+1}. {question_row[f'Option{i+1}'].values[0]}" for i in range(4)]
            
    #         # Add unified legend at bottom
    #         legend = legend_ax.legend(
    #             wedges1, labels,
    #             title="Response Options:",
    #             loc='center',
    #             ncol=4,
    #             frameon=False,
    #             fontsize=9
    #         )
    #         legend.get_title().set_fontsize(10)
            
    #         # Add main title with padding
    #         self.question_canvas.fig.suptitle(
    #             f"Question Analysis: {question_text}",
    #             y=0.95,
    #             fontsize=14,
    #             fontweight='bold'
    #         )
            
    #         # Store counts for hover
    #         self.your_counts = your_counts
    #         self.team_counts = team_counts
            
    #         # Adjust spacing
    #         self.question_canvas.fig.tight_layout()
    #         self.question_canvas.fig.subplots_adjust(top=0.85, bottom=0.15)
            
    #         self.question_canvas.draw()
    #     except Exception as e:
    #         QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

    # def plot_pie_chart(self, ax, data, title):
    #     """Helper function to plot pie charts and return counts"""
    #     # Initialize annotation
    #     ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
    #                         textcoords="offset points",
    #                         bbox=dict(boxstyle="round", fc="white", alpha=0.8),
    #                         arrowprops=dict(arrowstyle="->"))
    #     ax.annot.set_visible(False)
        
    #     # Get counts
    #     option_counts = data['response_value'].value_counts().sort_index()
    #     all_options = pd.Series([0]*4, index=[1,2,3,4])
    #     for idx, count in option_counts.items():
    #         if 1 <= idx <= 4:
    #             all_options[idx] = count
        
    #     # Plot pie chart
    #     wedges, texts, autotexts = ax.pie(
    #         all_options,
    #         labels=None,
    #         autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
    #         startangle=90,
    #         colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
    #         wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
    #         textprops={'color': 'black', 'fontsize': 8},
    #         pctdistance=0.85
    #     )
        
    #     # Add title with padding
    #     ax.set_title(title, fontsize=11, pad=20)
    #     ax.axis('equal')
        
    #     return wedges, all_options

    def pie_hover(self, event, ax):
        """Custom hover function showing counts and percentages"""
        if not event.inaxes == ax:
            ax.annot.set_visible(False)
            self.question_canvas.draw_idle()
            return
        
        for i, wedge in enumerate(ax.wedges):
            if wedge.contains_point((event.x, event.y)):
                counts = self.your_counts if ax.get_title() == "Your Responses" else self.team_counts
                total = counts.sum()
                percentage = (counts[i+1]/total)*100 if total > 0 else 0
                ax.annot.set_visible(True)
                ax.annot.set_text(f"Count: {counts[i+1]}\n({percentage:.1f}%)")
                theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
                r = wedge.r/2
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                ax.annot.xy = (x, y)
                self.question_canvas.draw_idle()
                return
        
        ax.annot.set_visible(False)
        self.question_canvas.draw_idle()


    def plot_pie_chart(self, ax, data, title):
        """Helper function to plot pie charts and return counts"""
        # Initialize annotation
        ax.annot = ax.annotate("", xy=(0,0), xytext=(20,20),
                            textcoords="offset points",
                            bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                            arrowprops=dict(arrowstyle="->"))
        ax.annot.set_visible(False)
        
        # Get counts
        option_counts = data['response_value'].value_counts().sort_index()
        all_options = pd.Series([0]*4, index=[1,2,3,4])
        for idx, count in option_counts.items():
            if 1 <= idx <= 4:
                all_options[idx] = count
        
        # Plot pie chart
        wedges, texts, autotexts = ax.pie(
            all_options,
            labels=None,
            autopct=lambda p: f'{p:.1f}%' if p > 0 else '',
            startangle=90,
            colors=cm.viridis(np.linspace(0.2, 0.8, 4)),
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
            textprops={'color': 'black', 'fontsize': 8},
            pctdistance=0.85
        )
        
        # Add title at bottom
        ax.text(0.5, -0.15, title, 
            ha='center', va='center',
            fontsize=11, transform=ax.transAxes)
        
        ax.axis('equal')
        
        return wedges, all_options

    def update_question_analysis(self, question_text):
        if self.merged_data is None or not question_text:
            return
        
        try:
            question_id = self.question_combo.currentData()
            
            # Split data into direct (you) and indirect (team)
            direct_data = self.merged_data[
                (self.merged_data['db_file'].str.contains(self.current_user)) &
                (self.merged_data['QuestionID'] == question_id)
            ]
            indirect_data = self.merged_data[
                (~self.merged_data['db_file'].str.contains(self.current_user)) &
                (self.merged_data['QuestionID'] == question_id)
            ]
            
            # Create figure with adjusted layout
            self.question_canvas.fig.clf()
            
            # Create gridspec
            gs = self.question_canvas.fig.add_gridspec(2, 2, width_ratios=[1, 1], height_ratios=[4, 1])
            ax1 = self.question_canvas.fig.add_subplot(gs[0, 0])
            ax2 = self.question_canvas.fig.add_subplot(gs[0, 1])
            legend_ax = self.question_canvas.fig.add_subplot(gs[1, :])
            legend_ax.axis('off')
            
            # Plot pie charts with new titles
            wedges1, direct_counts = self.plot_pie_chart(ax1, direct_data, "Direct")
            wedges2, indirect_counts = self.plot_pie_chart(ax2, indirect_data, "Indirect")
            
            # Get option labels
            question_row = self.questions_df[self.questions_df['QuestionID'] == question_id]
            labels = [f"{i+1}. {question_row[f'Option{i+1}'].values[0]}" for i in range(4)]
            
            # Add unified legend at bottom
            legend = legend_ax.legend(
                wedges1, labels,
                title="Response Options:",
                loc='center',
                ncol=4,
                frameon=False,
                fontsize=9
            )
            legend.get_title().set_fontsize(10)
            
            # Add main title
            self.question_canvas.fig.suptitle(
                f"Question Analysis: {question_text}",
                y=0.95,
                fontsize=14,
                fontweight='bold'
            )
            
            # Store counts for hover
            self.direct_counts = direct_counts
            self.indirect_counts = indirect_counts
            
            # Adjust spacing
            self.question_canvas.fig.tight_layout()
            self.question_canvas.fig.subplots_adjust(top=0.85, bottom=0.15)
            
            self.question_canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

