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
        self.viewing_team_data = False
        self.setWindowTitle(f"Survey Analysis - {current_user}")
        self.resize(1200, 900)  # Increased size for additional sections
        
        # Check if score chart should be visible
        self.score_chart_visible = (self.is_superuser or 
                                  self.reportee_count >= MIN_REPORTEES_FOR_SCORECHART)
        
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
            
        self.merged_data = None
        self.responses_df = None
        self.indirect_feedback_df = None
        self.general_feedback_df = None
        
        main_layout = QVBoxLayout()
        
        # User info and view toggle
        header_layout = QHBoxLayout()
        
        role_info = "Superuser" if is_superuser else f"Manager ({reportee_count} reportees)"
        user_info = QLabel(f"User: {current_user} | Role: {role_info}")
        user_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(user_info)
        
        # Only show team toggle if user has sufficient reportees or is superuser
        if (not is_superuser and manager_name and 
            (self.score_chart_visible or reportee_count > 0)):
            self.team_toggle = QCheckBox("View My Team's Data")
            self.team_toggle.setChecked(False)
            self.team_toggle.toggled.connect(self.toggle_team_view)
            header_layout.addWidget(self.team_toggle)
        
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        # Controls area
        controls_layout = QHBoxLayout()
        
        self.load_button = QPushButton("Refresh Data")
        style_buttons(self.load_button)
        self.load_button.clicked.connect(self.load_data)
        
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        
        # Create a splitter for main content
        splitter = QSplitter(Qt.Vertical)
        
        # Create tab widget for charts (only if score chart should be visible)
        if self.score_chart_visible:
            self.tabs = QTabWidget()
            self.create_overall_tab()
            self.create_section_tab()
            self.create_question_tab()
            splitter.addWidget(self.tabs)
        
        # Create feedback display area
        feedback_container = QWidget()
        feedback_layout = QVBoxLayout()
        
        # General Feedback section
        general_feedback_group = QGroupBox("General Feedback")
        general_feedback_layout = QVBoxLayout()
        self.general_feedback_display = QTextEdit()
        self.general_feedback_display.setReadOnly(True)
        general_feedback_layout.addWidget(self.general_feedback_display)
        general_feedback_group.setLayout(general_feedback_layout)
        feedback_layout.addWidget(general_feedback_group)
        
        # Indirect Feedback section (only for managers with reportees)
        if reportee_count > 0 or is_superuser:
            indirect_feedback_group = QGroupBox("Indirect Feedback from Reportees")
            indirect_feedback_layout = QVBoxLayout()
            self.indirect_feedback_display = QTextEdit()
            self.indirect_feedback_display.setReadOnly(True)
            indirect_feedback_layout.addWidget(self.indirect_feedback_display)
            indirect_feedback_group.setLayout(indirect_feedback_layout)
            feedback_layout.addWidget(indirect_feedback_group)
        
        feedback_container.setLayout(feedback_layout)
        splitter.addWidget(feedback_container)
        
        # Set splitter sizes (more space for charts if visible)
        if self.score_chart_visible:
            splitter.setSizes([600, 300])
        else:
            splitter.setSizes([0, 900])  # Show only feedback if no score chart
        
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(splitter)
        
        self.setLayout(main_layout)
        
        # Automatically load data
        self.load_data()
    
    def toggle_team_view(self, checked):
        """Toggle between individual and team view"""
        self.viewing_team_data = checked
        self.load_data()
        self.update_window_title()
    
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
        """Load data from ScoreData folder based on current view"""
        score_data_path = self.get_score_data_path()
        if not score_data_path:
            return

        try:
            if self.viewing_team_data and not self.is_superuser:
                # Load all files for the manager's team
                db_files = glob.glob(os.path.join(score_data_path, f"{self.manager_name}_*.db"))
            elif self.is_superuser:
                # Superuser sees all files
                db_files = glob.glob(os.path.join(score_data_path, "*.db"))
            else:
                # Load only files for the current user
                db_files = glob.glob(os.path.join(score_data_path, f"*_{self.current_user}.db"))
                
            if not db_files:
                QMessageBox.information(self, "No Data", "No survey data files found.")
                return
            
            all_responses = []
            all_general_feedback = []
            all_indirect_feedback = []
            
            for file in db_files:
                try:
                    conn = sqlite3.connect(file)
                    
                    # Load standard feedback
                    responses_df = pd.read_sql_query("SELECT * FROM Feedback WHERE feedback_type = 'LM'", conn)
                    responses_df['db_file'] = os.path.basename(file)
                    all_responses.append(responses_df)
                    
                    # Load general feedback
                    general_df = pd.read_sql_query(
                        "SELECT * FROM Feedback WHERE feedback_type = 'General'", 
                        conn
                    )
                    if not general_df.empty:
                        general_df['db_file'] = os.path.basename(file)
                        all_general_feedback.append(general_df)
                    
                    # Load indirect feedback (if any)
                    indirect_df = pd.read_sql_query(
                        "SELECT * FROM Feedback WHERE feedback_type = 'Indirect'", 
                        conn
                    )
                    if not indirect_df.empty:
                        indirect_df['db_file'] = os.path.basename(file)
                        all_indirect_feedback.append(indirect_df)
                    
                    conn.close()
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Could not load data from {file}: {str(e)}")
            
            try:
                # Process standard feedback
                if all_responses:
                    self.responses_df = pd.concat(all_responses)
                    self.responses_df['response_value'] = pd.to_numeric(
                        self.responses_df['response'], 
                        errors='coerce'
                    )
                    
                    # For non-numeric responses, map them to numeric values
                    if self.responses_df['response_value'].isna().any():
                        option_mapping = {}
                        for _, row in self.questions_df.iterrows():
                            for i in range(1, 5):
                                option_text = row[f'Option{i}']
                                option_mapping[option_text] = i
                        
                        self.responses_df['response_value'] = self.responses_df['response'].map(option_mapping)
                    
                    # Merge with question definitions
                    self.merged_data = pd.merge(
                        self.responses_df,
                        self.questions_df,
                        left_on='question_id',
                        right_on='QuestionID',
                        how='left'
                    )
                
                # Process general feedback
                if all_general_feedback:
                    self.general_feedback_df = pd.concat(all_general_feedback)
                    feedback_texts = self.general_feedback_df.groupby('employee_name')['response'].apply(
                        lambda x: "\n".join([f"- {text}" for text in x])
                    )
                    feedback_display = "\n\n".join(
                        [f"From {name}:\n{text}" for name, text in feedback_texts.items()]
                    )
                    self.general_feedback_display.setPlainText(feedback_display)
                else:
                    self.general_feedback_display.setPlainText("No general feedback available.")
                
                # Process indirect feedback
                if all_indirect_feedback:
                    self.indirect_feedback_df = pd.concat(all_indirect_feedback)
                    indirect_texts = self.indirect_feedback_df.groupby('employee_name')['response'].apply(
                        lambda x: "\n".join([f"- {text}" for text in x])
                    )
                    indirect_display = "\n\n".join(
                        [f"From {name}:\n{text}" for name, text in indirect_texts.items()]
                    )
                    if hasattr(self, 'indirect_feedback_display'):
                        self.indirect_feedback_display.setPlainText(indirect_display)
                elif hasattr(self, 'indirect_feedback_display'):
                    self.indirect_feedback_display.setPlainText("No indirect feedback available.")
                
                # Update analyses if score chart is visible
                if self.score_chart_visible:
                    self.update_overall_analysis()
                    self.update_section_analysis(self.section_combo.currentText())
                    self.update_question_analysis(self.question_combo.currentText())
                
                QMessageBox.information(
                    self, "Data Loaded", 
                    f"Loaded data from {len(db_files)} files\n"
                    f"Viewing: {'Team Data' if self.viewing_team_data else 'My Data'}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error processing data: {str(e)}")
        
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading data: {str(e)}")

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
    
    def update_overall_analysis(self):
        if self.merged_data is None:
            return

        try:
            self.overall_canvas.axes.clear()

            # Calculate average scores by category
            category_scores = self.merged_data.groupby('Category')['response_value'].mean()

            colors = cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
            bars = self.overall_canvas.axes.bar(category_scores.index, category_scores.values, color=colors)

            beautify_charts(self.overall_canvas.axes, 
                          f"{'Team' if self.viewing_team_data else 'My'} Overall Scores", 
                          ylabel='Average Score (1-4)')
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
            QMessageBox.warning(self, "Error", f"Error updating overall analysis: {str(e)}")

    def update_section_analysis(self, category):
        if self.merged_data is None:
            return
        
        try:
            self.section_canvas.axes.clear()
            
            category_data = self.merged_data[self.merged_data['Category'] == category]
            
            if category_data.empty:
                self.section_canvas.axes.text(0.5, 0.5, f"No data for {category} category",
                                            ha='center', va='center')
                self.section_canvas.draw()
                return
            
            question_scores = category_data.groupby(['QuestionID', 'Question'])['response_value'].mean()
            
            questions = [q[1] for q in question_scores.index]
            shortened_questions = [q[:20] + '...' if len(q) > 20 else q for q in questions]
            
            colors = cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
            bars = self.section_canvas.axes.bar(range(len(shortened_questions)), question_scores.values, color=colors)
            beautify_charts(self.section_canvas.axes, 
                          f"{category} Category - {'Team' if self.viewing_team_data else 'My'} Scores", 
                          ylabel='Average Score (1-4)')
            
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
            QMessageBox.warning(self, "Error", f"Error updating section analysis: {str(e)}")
    
    def update_question_analysis(self, question_text):
        if self.merged_data is None or not question_text:
            return
        
        try:
            question_id = self.question_combo.currentData()
            self.question_canvas.axes.clear()
            
            question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
            
            if question_data.empty:
                self.question_canvas.axes.text(0.5, 0.5, "No data for this question",
                                             ha='center', va='center')
                self.question_canvas.draw()
                return
            
            option_counts = question_data['response_value'].value_counts().sort_index()
            
            option_labels = []
            for i in range(1, 5):
                col_name = f'Option{i}'
                option_text = question_data[col_name].iloc[0] if not question_data.empty else f"Option {i}"
                option_labels.append(f"{i}: {option_text}")
            
            all_options = pd.Series([0, 0, 0, 0], index=[1, 2, 3, 4])
            for idx, count in option_counts.items():
                if idx > 0 and idx <= 4:
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
                    explode=[0.05, 0.05, 0.05, 0.05],
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
                
                self.question_canvas.axes.set_title(
                    f"{'Team' if self.viewing_team_data else 'My'} Responses: {question_text}"
                )
                self.question_canvas.axes.legend(wedges, option_labels, title="Options", 
                                               loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
                self.question_canvas.axes.axis('equal')
                
                self.question_canvas.annot = self.question_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
                                           textcoords="offset points",
                                           bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                           arrowprops=dict(arrowstyle="->"))
                self.question_canvas.annot.set_visible(False)
                
                self.question_canvas.fig.tight_layout()
                
            self.question_canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")


# In AnalysisApp class:

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
                reportees = self.get_direct_reportees()  # Implement this function
                for reportee in reportees:
                    db_files.extend(glob.glob(f"Feedback_{reportee}.db"))
            else:
                # Individual viewing their own feedback
                db_files = [f"Feedback_{self.current_user}.db"]
            
            # Load and process all relevant files
            all_feedback = []
            for db_file in set(db_files):  # Remove duplicates
                if os.path.exists(db_file):
                    with sqlite3.connect(db_file) as conn:
                        df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE is_aggregated=0", 
                            conn
                        )
                        all_feedback.append(df)
            
            if not all_feedback:
                self.show_no_data_message()
                return
            
            self.feedback_df = pd.concat(all_feedback)
            
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
                
                if manager_feedback:
                    self.manager_feedback_df = pd.concat(manager_feedback)
                else:
                    self.manager_feedback_df = pd.DataFrame()
            
            self.update_analyses()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")

    def get_direct_reportees(self):
        """Get list of direct reportees from hierarchy"""
        try:
            df = pd.read_excel('employee_hierarchy.xlsx')
            return df[df['Manager'] == self.current_user]['Reportee'].unique().tolist()
        except Exception as e:
            print(f"Error getting reportees: {e}")
            return []

    def update_analyses(self):
        """Update all analysis views based on current data"""
        if not hasattr(self, 'feedback_df') or self.feedback_df.empty:
            self.show_no_data_message()
            return
        
        # Update overall analysis
        if self.score_chart_visible:
            self.update_overall_analysis()
        
        # Update feedback displays
        self.update_feedback_displays()
        
        # Special message for managers with few reportees
        if (not self.is_superuser and 
            self.reportee_count < MIN_REPORTEES_FOR_SCORECHART and
            not self.viewing_team_data):
            
            msg = ("Note: As you have fewer than 2 direct reportees, your individual feedback\n"
                "has been included in your manager's analysis instead.")
            self.status_label.setText(msg)

