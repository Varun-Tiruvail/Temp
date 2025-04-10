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
                           QFileDialog, QMessageBox, QScrollArea, QGroupBox,
                           QGridLayout, QSplitter, QCheckBox, QTextEdit)
from PyQt5.QtCore import Qt
import matplotlib
from matplotlib import cm
from PyQt5.QtGui import QFont
matplotlib.use('Qt5Agg')

# Configuration
MIN_REPORTEES_FOR_SCORECHART = 2

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
        self.viewing_team_data = False
        
        # Initialize empty DataFrames
        self.feedback_df = pd.DataFrame()
        self.manager_feedback_df = pd.DataFrame()
        self.general_feedback_df = pd.DataFrame()
        self.indirect_feedback_df = pd.DataFrame()
        self.general_feedback_display = None
        self.indirect_feedback_display = None
        
        self.setWindowTitle(f"Survey Analysis - {current_user}")
        self.resize(1200, 900)
        
        # Check if score chart should be visible
        self.score_chart_visible = (self.is_superuser or 
                                  self.reportee_count >= MIN_REPORTEES_FOR_SCORECHART)
        
        # Load questions
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
            required_columns = ['QuestionID', 'Category', 'Question', 
                              'Option1', 'Option2', 'Option3', 'Option4']
            
            column_alternatives = {
                'QuestionID': ['QuestionID', 'Question_ID', 'Id', 'ID'],
                'Category': ['Category', 'Section', 'Type'],
                'Question': ['Question', 'QuestionText', 'Text'],
                'Option1': ['Option1', 'Option_1', 'Choice1'],
                'Option2': ['Option2', 'Option_2', 'Choice2'],
                'Option3': ['Option3', 'Option_3', 'Choice3'],
                'Option4': ['Option4', 'Option_4', 'Choice4']
            }
            
            actual_columns = self.questions_df.columns.tolist()
            for expected, alternatives in column_alternatives.items():
                if expected not in actual_columns:
                    for alt in alternatives:
                        if alt in actual_columns:
                            self.questions_df.rename(columns={alt: expected}, inplace=True)
                            break
            
            missing_columns = [col for col in required_columns if col not in self.questions_df.columns]
            if missing_columns:
                raise KeyError(f"Missing required columns: {', '.join(missing_columns)}")
                
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found!")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions file: {str(e)}")
            sys.exit(1)
            
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        main_layout = QVBoxLayout()
        
        # Header with user info
        header_layout = QHBoxLayout()
        
        role_info = "Superuser" if self.is_superuser else f"Manager ({self.reportee_count} reportees)" if self.reportee_count > 0 else "Employee"
        user_info = QLabel(f"User: {self.current_user} | Role: {role_info}")
        user_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(user_info)
        
        # Team toggle for managers
        if (not self.is_superuser and self.manager_name and 
            (self.score_chart_visible or self.reportee_count > 0)):
            self.team_toggle = QCheckBox("View My Team's Data")
            self.team_toggle.setChecked(False)
            self.team_toggle.toggled.connect(self.toggle_team_view)
            header_layout.addWidget(self.team_toggle)
        
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        # Status label
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.status_label)
        
        # Controls
        controls_layout = QHBoxLayout()
        self.load_button = QPushButton("Refresh Data")
        style_buttons(self.load_button)
        self.load_button.clicked.connect(self.load_data)
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Vertical)
        
        # Create tab widget for charts if score chart is visible
        if self.score_chart_visible:
            self.tabs = QTabWidget()
            self.create_overall_tab()
            self.create_section_tab()
            self.create_question_tab()
            splitter.addWidget(self.tabs)
        
        # # Create feedback display area
        # feedback_container = QWidget()
        # feedback_layout = QVBoxLayout()
        
        # # General Feedback section
        # general_feedback_group = QGroupBox("General Feedback")
        # general_feedback_layout = QVBoxLayout()
        # self.general_feedback_display = QTextEdit()
        # self.general_feedback_display.setReadOnly(True)
        # general_feedback_layout.addWidget(self.general_feedback_display)
        # general_feedback_group.setLayout(general_feedback_layout)
        # feedback_layout.addWidget(general_feedback_group)
        
        # # Indirect Feedback section (for managers)
        # if self.reportee_count > 0 or self.is_superuser:
        #     indirect_feedback_group = QGroupBox("Indirect Feedback from Reportees")
        #     indirect_feedback_layout = QVBoxLayout()
        #     self.indirect_feedback_display = QTextEdit()
        #     self.indirect_feedback_display.setReadOnly(True)
        #     indirect_feedback_layout.addWidget(self.indirect_feedback_display)
        #     indirect_feedback_group.setLayout(indirect_feedback_layout)
        #     feedback_layout.addWidget(indirect_feedback_group)
        
        # feedback_container.setLayout(feedback_layout)
        # splitter.addWidget(feedback_container)

        # Create feedback display area
        feedback_container = QWidget()
        feedback_layout = QVBoxLayout()

        # Initialize general feedback display
        general_feedback_group = QGroupBox("General Feedback")
        general_feedback_layout = QVBoxLayout()
        self.general_feedback_display = QTextEdit()  # Proper initialization
        self.general_feedback_display.setReadOnly(True)
        general_feedback_layout.addWidget(self.general_feedback_display)
        general_feedback_group.setLayout(general_feedback_layout)
        feedback_layout.addWidget(general_feedback_group)

        # Initialize indirect feedback display
        if self.reportee_count > 0 or self.is_superuser:
            indirect_feedback_group = QGroupBox("Indirect Feedback from Reportees")
            indirect_feedback_layout = QVBoxLayout()
            self.indirect_feedback_display = QTextEdit()  # Proper initialization
            self.indirect_feedback_display.setReadOnly(True)
            indirect_feedback_layout.addWidget(self.indirect_feedback_display)
            indirect_feedback_group.setLayout(indirect_feedback_layout)
            feedback_layout.addWidget(indirect_feedback_group)

        feedback_container.setLayout(feedback_layout)
        splitter.addWidget(feedback_container)
        
        # Set splitter sizes
        if self.score_chart_visible:
            splitter.setSizes([600, 300])
        else:
            splitter.setSizes([0, 900])  # Show only feedback if no score chart
        
        main_layout.addWidget(splitter)
        self.setLayout(main_layout)
    
    def show_no_data_message(self):
        """Display message when no feedback data is available"""
        if hasattr(self, 'overall_canvas'):
            self.overall_canvas.axes.clear()
            self.overall_canvas.axes.text(0.5, 0.5, 
                                         "No feedback data available\n"
                                         "Please submit feedback first",
                                         ha='center', va='center')
            self.overall_canvas.draw()
        
        if hasattr(self, 'section_canvas'):
            self.section_canvas.axes.clear()
            self.section_canvas.draw()
        
        if hasattr(self, 'question_canvas'):
            self.question_canvas.axes.clear()
            self.question_canvas.draw()
        
        # self.general_feedback_display.setPlainText("No general feedback available")
        
        # if hasattr(self, 'indirect_feedback_display'):
        #     self.indirect_feedback_display.setPlainText("No indirect feedback available")
        if hasattr(self, 'general_feedback_display') and self.general_feedback_display:
            self.general_feedback_display.setPlainText("No general feedback available")
        
        if hasattr(self, 'indirect_feedback_display') and self.indirect_feedback_display:
            self.indirect_feedback_display.setPlainText("No indirect feedback available")
        
        self.status_label.setText("No feedback data found for current view")
    
    def get_direct_reportees(self):
        """Get list of direct reportees from hierarchy"""
        try:
            df = pd.read_excel('employee_hierarchy.xlsx')
            return df[df['Manager'] == self.current_user]['Reportee'].unique().tolist()
        except Exception as e:
            print(f"Error getting reportees: {e}")
            return []
    
    def toggle_team_view(self, checked):
        """Toggle between individual and team view"""
        self.viewing_team_data = checked
        self.load_data()
        self.update_window_title()
    
    def update_window_title(self):
        """Update window title based on current view"""
        if self.viewing_team_data:
            self.setWindowTitle(f"Survey Analysis - {self.current_user}'s Team")
        else:
            self.setWindowTitle(f"Survey Analysis - {self.current_user}")
    
    def load_data(self):
        """Load and aggregate feedback data based on user's position"""
        try:
            # Determine which feedback files to load
            if self.is_superuser:
                # Superuser sees all feedback
                db_files = glob.glob("Feedback_*.db")
            elif self.viewing_team_data:
                # Manager viewing team data - load their direct reportees' feedback
                db_files = [f"Feedback_{self.current_user}.db"]  # Their own feedback
                reportees = self.get_direct_reportees()
                for reportee in reportees:
                    db_files.extend(glob.glob(f"Feedback_{reportee}.db"))
            else:
                # Individual viewing their own feedback
                db_files = [f"Feedback_{self.current_user}.db"]
            
            # Load and process all relevant files
            all_feedback = []
            all_general = []
            all_indirect = []
            
            for db_file in set(db_files):  # Remove duplicates
                if os.path.exists(db_file):
                    with sqlite3.connect(db_file) as conn:
                        # Load standard feedback
                        df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE is_aggregated=0 AND feedback_type='LM'", 
                            conn
                        )
                        if not df.empty:
                            all_feedback.append(df)
                        
                        # Load general feedback
                        gen_df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE feedback_type='General'", 
                            conn
                        )
                        if not gen_df.empty:
                            all_general.append(gen_df)
                        
                        # Load indirect feedback
                        ind_df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE feedback_type='Indirect'", 
                            conn
                        )
                        if not ind_df.empty:
                            all_indirect.append(ind_df)
            
            # Combine all data
            self.feedback_df = pd.concat(all_feedback) if all_feedback else pd.DataFrame()
            self.general_feedback_df = pd.concat(all_general) if all_general else pd.DataFrame()
            self.indirect_feedback_df = pd.concat(all_indirect) if all_indirect else pd.DataFrame()
            
            # Special handling for managers with few reportees
            if (not self.is_superuser and 
                self.reportee_count < MIN_REPORTEES_FOR_SCORECHART and
                not self.viewing_team_data):
                
                # Load manager's aggregated feedback
                manager_feedback = []
                if self.manager_name:
                    manager_db = f"Feedback_{self.manager_name}.db"
                    if os.path.exists(manager_db):
                        with sqlite3.connect(manager_db) as conn:
                            df = pd.read_sql_query(
                                '''SELECT * FROM feedback_responses 
                                   WHERE employee_name=? AND is_aggregated=1''',
                                conn, params=(self.current_user,)
                            )
                            manager_feedback.append(df)
                
                self.manager_feedback_df = pd.concat(manager_feedback) if manager_feedback else pd.DataFrame()
            
            # Update displays
            if not self.feedback_df.empty or not self.manager_feedback_df.empty:
                self.update_analyses()
            else:
                self.show_no_data_message()
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
    
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
        self.section_combo.addItems(["Cultural", "Development", "Ways of Working"])
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
    
    def update_analyses(self):
        """Update all analysis views based on current data"""
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
        """Update the text feedback displays"""
        # General feedback
        if not self.general_feedback_df.empty:
            feedback_texts = self.general_feedback_df.groupby('employee_name')['response_text'].apply(
                lambda x: "\n".join([f"- {text}" for text in x])
            )
            feedback_display = "\n\n".join(
                [f"From {name}:\n{text}" for name, text in feedback_texts.items()]
            )
            self.general_feedback_display.setPlainText(feedback_display)
        else:
            self.general_feedback_display.setPlainText("No general feedback available")
        
        # Indirect feedback
        if hasattr(self, 'indirect_feedback_display'):
            if not self.indirect_feedback_df.empty:
                feedback_texts = self.indirect_feedback_df.groupby('employee_name')['response_text'].apply(
                    lambda x: "\n".join([f"- {text}" for text in x])
                )
                feedback_display = "\n\n".join(
                    [f"From {name}:\n{text}" for name, text in feedback_texts.items()]
                )
                self.indirect_feedback_display.setPlainText(feedback_display)
            else:
                self.indirect_feedback_display.setPlainText("No indirect feedback available")
    
    def update_overall_analysis(self):
        if not hasattr(self, 'feedback_df') or self.feedback_df.empty:
            self.show_no_data_message()
            return

        try:
            self.overall_canvas.axes.clear()

            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            # Calculate average scores by category
            category_scores = combined_df.groupby('category')['response_value'].mean()

            colors = cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
            bars = self.overall_canvas.axes.bar(category_scores.index, category_scores.values, color=colors)

            title = f"{'Team' if self.viewing_team_data else 'My'} Overall Scores"
            if not self.manager_feedback_df.empty:
                title += " (Including manager's view)"
                
            beautify_charts(self.overall_canvas.axes, title, ylabel='Average Score (1-4)')
            self.overall_canvas.axes.set_ylim(0, 4)

            for bar in bars:
                height = bar.get_height()
                self.overall_canvas.axes.text(
                    bar.get_x() + bar.get_width() / 2., height + 0.1,
                    f'{height:.2f}', ha='center', va='bottom', fontsize=10, color='#333333'
                )

            self.overall_canvas.fig.tight_layout()
            self.overall_canvas.draw()
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Error", f"Error updating overall analysis: {str(e)}")

    def update_section_analysis(self, category):
        if not hasattr(self, 'feedback_df') or self.feedback_df.empty:
            self.show_no_data_message()
            return
        
        try:
            self.section_canvas.axes.clear()
            
            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            category_data = combined_df[combined_df['category'] == category]
            
            if category_data.empty:
                self.section_canvas.axes.text(0.5, 0.5, f"No data for {category} category",
                                            ha='center', va='center')
                self.section_canvas.draw()
                return
            
            question_scores = category_data.groupby(['question_id', 'question'])['response_value'].mean()
            
            questions = [q[1] for q in question_scores.index]
            shortened_questions = [q[:20] + '...' if len(q) > 20 else q for q in questions]
            
            colors = cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
            bars = self.section_canvas.axes.bar(range(len(shortened_questions)), question_scores.values, color=colors)
            
            title = f"{category} Category - {'Team' if self.viewing_team_data else 'My'} Scores"
            if not self.manager_feedback_df.empty:
                title += " (Including manager's view)"
                
            beautify_charts(self.section_canvas.axes, title, ylabel='Average Score (1-4)')
            
            self.section_canvas.axes.set_ylim(0, 4)
            self.section_canvas.axes.set_xticks(range(len(shortened_questions)))
            self.section_canvas.axes.set_xticklabels(shortened_questions, rotation=45, ha='right')
            
            self.section_canvas.bar_labels = questions
            self.section_canvas.bars = bars
            
            self.section_canvas.annot = self.section_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
                                   textcoords="offset points",
                                   bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                   arrowprops=dict(arrowstyle="->"))
            self.section_canvas.annot.set_visible(False)
            
            def hover(event):
                if not event.inaxes:
                    return

                for i, bar in enumerate(bars):
                    if bar.contains_point([event.x, event.y]):
                        self.section_canvas.annot.set_visible(True)
                        self.section_canvas.annot.set_text(f"{questions[i]}\nScore: {question_scores.values[i]:.2f}")
                        self.section_canvas.annot.xy = (bar.get_x() + bar.get_width() / 2, bar.get_height())
                        self.section_canvas.draw_idle()
                        return

                self.section_canvas.annot.set_visible(False)
                self.section_canvas.draw_idle()
            
            self.section_canvas.hover = hover
            self.section_canvas.fig.canvas.mpl_connect("motion_notify_event", self.section_canvas.hover)
            
            self.section_canvas.fig.tight_layout()
            self.section_canvas.draw()
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Error", f"Error updating section analysis: {str(e)}")
    
    def update_question_analysis(self, question_text):
        if not hasattr(self, 'feedback_df') or self.feedback_df.empty or not question_text:
            self.show_no_data_message()
            return
        
        try:
            question_id = self.question_combo.currentData()
            self.question_canvas.axes.clear()
            
            # Combine with manager feedback if applicable
            combined_df = pd.concat([self.feedback_df, self.manager_feedback_df]) if not self.manager_feedback_df.empty else self.feedback_df
            
            question_data = combined_df[combined_df['question_id'] == question_id]
            
            if question_data.empty:
                self.question_canvas.axes.text(0.5, 0.5, "No data for this question",
                                             ha='center', va='center')
                self.question_canvas.draw()
                return
            
            option_counts = question_data['response_value'].value_counts().sort_index()
            
            # Get option texts from questions_df
            question_row = self.questions_df[self.questions_df['QuestionID'] == question_id].iloc[0]
            option_labels = []
            for i in range(1, 5):
                option_text = question_row[f'Option{i}']
                option_labels.append(f"{i}: {option_text}")
            
            # Ensure we have counts for all options (1-4)
            all_options = pd.Series([0]*4, index=[1,2,3,4])
            for idx, count in option_counts.items():
                if idx in all_options.index:
                    all_options[idx] = count
            
            if all_options.sum() == 0:
                self.question_canvas.axes.text(0.5, 0.5, "No responses for this question",
                                             ha='center', va='center')
                self.question_canvas.draw()
            else:
                wedges, _ = self.question_canvas.axes.pie(
                    all_options, 
                    labels=None,
                    autopct=None,
                    startangle=90,
                    explode=[0.05]*4,
                    shadow=True,
                    wedgeprops={'linewidth': 1, 'edgecolor': 'white'},
                    colors=cm.viridis(np.linspace(0.2, 0.8, 4))
                )
                
                self.question_canvas.pie_wedges = wedges
                
                total = all_options.sum()
                detailed_labels = []
                for i, (label, count) in enumerate(zip(option_labels, all_options)):
                    percentage = (count / total) * 100 if total > 0 else 0
                    detailed_labels.append(f"{label}\nCount: {count}\n({percentage:.1f}%)")
                
                self.question_canvas.pie_labels = detailed_labels
                
                title = f"{'Team' if self.viewing_team_data else 'My'} Responses: {question_text}"
                if not self.manager_feedback_df.empty:
                    title += " (Including manager's view)"
                
                self.question_canvas.axes.set_title(title)
                self.question_canvas.axes.legend(wedges, option_labels, title="Options", 
                                               loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
                self.question_canvas.axes.axis('equal')
                self.question_canvas.fig.tight_layout()
                
            self.question_canvas.draw()
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")