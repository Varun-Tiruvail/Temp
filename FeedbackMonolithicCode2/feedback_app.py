import sys
import os
import glob
import sqlite3
import datetime
import pandas as pd
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib import cm
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QMessageBox,
    QStackedWidget, QComboBox, QDialog, QTableWidget, QTableWidgetItem, QScrollArea,
    QGroupBox, QTextEdit, QApplication, QFileDialog, QTabWidget, QSplitter, QCheckBox,
    QRadioButton, QButtonGroup, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont

matplotlib.use('Qt5Agg')

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

# Database Functions
def create_connection(db_file):
    """Create a database connection to a SQLite database"""
    conn = None
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except Exception as e:
        print(e)
    return conn

def initialize_databases():
    """ Initialize both temporary and final databases """
    # Temporary database for pending approvals
    temp_conn = create_connection('temp_database.db')
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            manager TEXT NOT NULL,
            is_approved INTEGER DEFAULT 0
        )
    ''')
    temp_conn.commit()
    
    # Final database for approved users
    final_conn = create_connection('final_database.db')
    final_cursor = final_conn.cursor()
    final_cursor.execute('''
        CREATE TABLE IF NOT EXISTS approved_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            manager TEXT NOT NULL,
            is_superuser INTEGER DEFAULT 0
        )
    ''')
    
    # Add superuser if not exists
    final_cursor.execute("SELECT * FROM approved_users WHERE username='Admin'")
    if not final_cursor.fetchone():
        final_cursor.execute(
            "INSERT INTO approved_users (username, password, manager, is_superuser) VALUES (?, ?, ?, ?)",
            ('Admin', 'mnbvcxz!@#098', 'None', 1)
        )
    final_conn.commit()
    
    temp_conn.close()
    final_conn.close()

def check_hierarchy(username):
    """Check if username exists in the hierarchy"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        return username in df['Manager'].values or username in df['Reportee'].values
    except Exception as e:
        print(f"Error reading hierarchy file: {e}")
        return False

def get_manager(username):
    """Get manager for a given username from hierarchy"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        manager = df[df['Reportee'] == username]['Manager'].values
        return manager[0] if len(manager) > 0 else None
    except Exception as e:
        print(f"Error getting manager: {e}")
        return None

def add_pending_user(username, password, manager):
    """ Add user to temporary database for approval """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO pending_users (username, password, manager) VALUES (?, ?, ?)",
        (username, password, manager)
    )
    conn.commit()
    conn.close()

def validate_login(username, password):
    """Validate user credentials with reportee count"""
    try:
        with sqlite3.connect('final_database.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT username, manager, is_superuser FROM approved_users WHERE username=? AND password=?",
                (username, password)
            )
            user = cursor.fetchone()
            if user:
                reportee_count = get_reportee_count(username)
                return (*user, reportee_count)  # Returns tuple (username, manager, is_superuser, reportee_count)
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    return None

def get_reportee_count(username):
    """Count how many direct reportees a user has"""
    try:
        df = pd.read_excel('employee_hierarchy.xlsx')
        return len(df[df['Manager'] == username]['Reportee'].unique())
    except Exception as e:
        print(f"Error counting reportees: {e}")
        return 0

def get_pending_approvals(manager_username=None):
    """ Get pending approvals - for specific manager or all if None """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    
    if manager_username:
        cursor.execute(
            "SELECT id, username, manager FROM pending_users WHERE manager=? AND is_approved=0",
            (manager_username,)
        )
    else:
        cursor.execute(
            "SELECT id, username, manager FROM pending_users WHERE is_approved=0"
        )
    
    approvals = cursor.fetchall()
    conn.close()
    return approvals

def approve_user(user_id):
    """ Approve a user and move to final database """
    temp_conn = create_connection('temp_database.db')
    final_conn = create_connection('final_database.db')
    
    # Get user from temp database
    temp_cursor = temp_conn.cursor()
    temp_cursor.execute(
        "SELECT username, password, manager FROM pending_users WHERE id=?",
        (user_id,)
    )
    user = temp_cursor.fetchone()
    
    if user:
        # Add to final database
        final_cursor = final_conn.cursor()
        final_cursor.execute(
            "INSERT INTO approved_users (username, password, manager) VALUES (?, ?, ?)",
            user
        )
        final_conn.commit()
        
        # Remove from temp database
        temp_cursor.execute(
            "DELETE FROM pending_users WHERE id=?",
            (user_id,)
        )
        temp_conn.commit()
    
    temp_conn.close()
    final_conn.close()

def disapprove_user(user_id):
    """ Remove user from temporary database (disapproval) """
    conn = create_connection('temp_database.db')
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM pending_users WHERE id=?",
        (user_id,)
    )
    conn.commit()
    conn.close()

# GUI Classes
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
        
        self.approval_table = QTableWidget()
        self.approval_table.setColumnCount(3)
        self.approval_table.setHorizontalHeaderLabels(['ID', 'Username', 'Manager'])
        self.approval_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.approval_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.approval_table)
        
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
        approvals = get_pending_approvals(None if self.is_superuser else self.current_user)
        
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
        
        for user_id in selected:
            approve_user(user_id)
        
        QMessageBox.information(self, 'Success', f'Approved {len(selected)} user(s)')
        self.load_pending_approvals()
    
    def disapprove_selected(self):
        selected = self.get_selected_ids()
        if not selected:
            QMessageBox.warning(self, 'Error', 'Please select at least one user')
            return
        
        reply = QMessageBox.question(
            self, 'Confirm Disapproval',
            f'Are you sure you want to disapprove {len(selected)} user(s)?\n\nThis action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for user_id in selected:
                disapprove_user(user_id)
            
            QMessageBox.information(self, 'Success', f'Disapproved {len(selected)} user(s)')
            self.load_pending_approvals()
    
    def get_selected_ids(self):
        selected_ids = []
        for item in self.approval_table.selectedItems():
            if item.column() == 0:
                selected_ids.append(int(item.text()))
        return list(set(selected_ids))

class SurveyApp(QDialog):
    def __init__(self, current_user, manager_name):
        super().__init__()
        self.current_user = current_user
        self.manager_name = manager_name
        self.setWindowTitle(f"Feedback Survey - {current_user}")
        self.resize(800, 600)
        self.questions_df = self.load_questions()
        self.lm_responses = {}
        self.create_ui()
    
    def load_questions(self):
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
        main_layout = QVBoxLayout()
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
        
        self.stacked_widget = QStackedWidget()
        self.create_lm_feedback_page()
        self.create_general_feedback_page()
        main_layout.addWidget(self.stacked_widget)
        
        self.submit_button = QPushButton("Submit Feedback")
        self.submit_button.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 10px; }"
            "QPushButton:hover { background-color: #45a049; }"
        )
        self.submit_button.clicked.connect(self.submit_feedback)
        main_layout.addWidget(self.submit_button)
        self.setLayout(main_layout)
    
    def create_lm_feedback_page(self):
        page = QWidget()
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout()
        
        categories = self.questions_df['Category'].unique()
        for category in categories:
            category_group = QGroupBox(category)
            category_layout = QVBoxLayout()
            
            for _, row in self.questions_df[self.questions_df['Category'] == category].iterrows():
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
                category_layout.addWidget(question_group)
            
            category_group.setLayout(category_layout)
            container_layout.addWidget(category_group)
        
        container.setLayout(container_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)
        page.setLayout(layout)
        self.stacked_widget.addWidget(page)
    
    def set_response(self, question_id, value):
        self.lm_responses[question_id] = value
    
    def create_general_feedback_page(self):
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
        db_filename = f"Feedback_{self.manager_name}.db" if self.manager_name else "Feedback_General.db"
        
        try:
            with sqlite3.connect(db_filename) as conn:
                cursor = conn.cursor()
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
                
                general_feedback = self.general_feedback_input.toPlainText().strip()
                if general_feedback:
                    cursor.execute(
                        '''INSERT INTO feedback_responses 
                        (feedback_type, question_id, category, response_value,
                         response_text, employee_name, timestamp)
                        VALUES (?, ?, ?, ?, ?, ?, ?)''',
                        ('General', 'N/A', 'N/A', 0, general_feedback, self.current_user, current_time)
                    )
                
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
            QMessageBox.critical(self, "Error", f"Failed to submit feedback: {str(e)}")

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
        self.feedback_df = pd.DataFrame()
        self.manager_feedback_df = pd.DataFrame()
        self.general_feedback_df = pd.DataFrame()
        self.indirect_feedback_df = pd.DataFrame()
        # Add these initialization lines
        self.general_feedback_display = None
        self.indirect_feedback_display = None
        self.setWindowTitle(f"Survey Analysis - {current_user}")
        self.resize(1200, 900)
        self.score_chart_visible = (self.is_superuser or self.reportee_count >= 2)
        
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
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
            
            missing_columns = [col for col in self.questions_df.columns if col not in actual_columns]
            if missing_columns:
                raise KeyError(f"Missing required columns: {', '.join(missing_columns)}")
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions file: {str(e)}")
            sys.exit(1)
            
        self.init_ui()
        self.load_data()
    
    def init_ui(self):
        main_layout = QVBoxLayout()
        header_layout = QHBoxLayout()
        role_info = "Superuser" if self.is_superuser else f"Manager ({self.reportee_count} reportees)" if self.reportee_count > 0 else "Employee"
        user_info = QLabel(f"User: {self.current_user} | Role: {role_info}")
        user_info.setStyleSheet("font-weight: bold; font-size: 14px;")
        header_layout.addWidget(user_info)
        
        if (not self.is_superuser and self.manager_name and (self.score_chart_visible or self.reportee_count > 0)):
            self.team_toggle = QCheckBox("View My Team's Data")
            self.team_toggle.setChecked(False)
            self.team_toggle.toggled.connect(self.toggle_team_view)
            header_layout.addWidget(self.team_toggle)
        
        header_layout.addStretch(1)
        main_layout.addLayout(header_layout)
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        main_layout.addWidget(self.status_label)
        
        controls_layout = QHBoxLayout()
        self.load_button = QPushButton("Refresh Data")
        self.load_button.clicked.connect(self.load_data)
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        main_layout.addLayout(controls_layout)
        
        splitter = QSplitter(Qt.Vertical)
        
        if self.score_chart_visible:
            self.tabs = QTabWidget()
            self.create_overall_tab()
            self.create_section_tab()
            self.create_question_tab()
            splitter.addWidget(self.tabs)
        
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
    
    # def show_no_data_message(self):
    #     """Display message when no feedback data is available"""
    #     if hasattr(self, 'overall_canvas'):
    #         self.overall_canvas.axes.clear()
    #         self.overall_canvas.axes.text(0.5, 0.5, 
    #                                      "No feedback data available\n"
    #                                      "Please submit feedback first",
    #                                      ha='center', va='center')
    #         self.overall_canvas.draw()
        
    #     if hasattr(self, 'section_canvas'):
    #         self.section_canvas.axes.clear()
    #         self.section_canvas.draw()
        
    #     if hasattr(self, 'question_canvas'):
    #         self.question_canvas.axes.clear()
    #         self.question_canvas.draw()
        
    #     """Display message when no feedback data is available"""
    #     if hasattr(self, 'general_feedback_display') and self.general_feedback_display:
    #         self.general_feedback_display.setPlainText("No general feedback available")
        
    #     if hasattr(self, 'indirect_feedback_display') and self.indirect_feedback_display:
    #         self.indirect_feedback_display.setPlainText("No indirect feedback available")
        
    #     self.status_label.setText("No feedback data found for current view")
    
    def show_no_data_message(self):
        """Display message when no feedback data is available"""
        try:
            # Check if canvas exists and is valid before using
            if hasattr(self, 'overall_canvas') and self._is_canvas_valid(self.overall_canvas):
                self.overall_canvas.axes.clear()
                self.overall_canvas.axes.text(
                    0.5, 0.5,
                    "No feedback data available\nPlease submit feedback first",
                    ha='center', va='center'
                )
                self._safe_draw(self.overall_canvas)

            if hasattr(self, 'section_canvas') and self._is_canvas_valid(self.section_canvas):
                self.section_canvas.axes.clear()
                self._safe_draw(self.section_canvas)

            if hasattr(self, 'question_canvas') and self._is_canvas_valid(self.question_canvas):
                self.question_canvas.axes.clear()
                self._safe_draw(self.question_canvas)

        except Exception as e:
            print(f"Error showing no data message: {str(e)}")
        
        # Safe text display
        try:
            if hasattr(self, 'general_feedback_display'):
                self.general_feedback_display.setPlainText("No general feedback available")
        except RuntimeError:
            pass

        try:
            if hasattr(self, 'indirect_feedback_display'):
                self.indirect_feedback_display.setPlainText("No indirect feedback available")
        except RuntimeError:
            pass

        self.status_label.setText("No feedback data found for current view")
    def _is_canvas_valid(self, canvas):
        """Check if a canvas widget is still valid"""
        try:
            # Check if the C++ object still exists
            return canvas is not None and canvas.isValid()
        except RuntimeError:
            return False

    def _safe_draw(self, canvas):
        """Safe wrapper for canvas drawing"""
        try:
            if self._is_canvas_valid(canvas):
                canvas.draw()
        except Exception as e:
            print(f"Error drawing canvas: {str(e)}")

    def closeEvent(self, event):
        """Clean up resources when closing the dialog"""
        # Explicitly clear matplotlib figures
        if hasattr(self, 'overall_canvas'):
            self.overall_canvas.fig.clf()
            plt.close(self.overall_canvas.fig)
        
        if hasattr(self, 'section_canvas'):
            self.section_canvas.fig.clf()
            plt.close(self.section_canvas.fig)
            
        if hasattr(self, 'question_canvas'):
            self.question_canvas.fig.clf()
            plt.close(self.question_canvas.fig)
            
        super().closeEvent(event)
    

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
        try:
            if self.is_superuser:
                db_files = glob.glob("Feedback_*.db")
            elif self.viewing_team_data:
                db_files = [f"Feedback_{self.current_user}.db"]
                reportees = self.get_direct_reportees()
                for reportee in reportees:
                    db_files.extend(glob.glob(f"Feedback_{reportee}.db"))
            else:
                db_files = [f"Feedback_{self.current_user}.db"]
            
            all_feedback = []
            all_general = []
            all_indirect = []
            
            for db_file in set(db_files):
                if os.path.exists(db_file):
                    with sqlite3.connect(db_file) as conn:
                        df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE is_aggregated=0 AND feedback_type='LM'", 
                            conn
                        )
                        if not df.empty:
                            all_feedback.append(df)
                        
                        gen_df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE feedback_type='General'", 
                            conn
                        )
                        if not gen_df.empty:
                            all_general.append(gen_df)
                        
                        ind_df = pd.read_sql_query(
                            "SELECT * FROM feedback_responses WHERE feedback_type='Indirect'", 
                            conn
                        )
                        if not ind_df.empty:
                            all_indirect.append(ind_df)
            
            self.feedback_df = pd.concat(all_feedback) if all_feedback else pd.DataFrame()
            self.general_feedback_df = pd.concat(all_general) if all_general else pd.DataFrame()
            self.indirect_feedback_df = pd.concat(all_indirect) if all_indirect else pd.DataFrame()
            
            if (not self.is_superuser and self.reportee_count < 2 and not self.viewing_team_data):
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
            
            if not self.feedback_df.empty or not self.manager_feedback_df.empty:
                self.update_analyses()
            else:
                self.show_no_data_message()
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.critical(self, "Error", f"Failed to load data: {str(e)}")
    
    def update_analyses(self):
        try:
            if self.score_chart_visible:
                self.update_overall_analysis()
            
            if hasattr(self, 'section_combo'):
                self.update_section_analysis(self.section_combo.currentText())
            
            if hasattr(self, 'question_combo') and self.question_combo.count() > 0:
                self.update_question_analysis(self.question_combo.currentText())
            
            self.update_feedback_displays()
            
            if (not self.is_superuser and self.reportee_count < 2 and not self.viewing_team_data):
                self.status_label.setText("Note: As you have fewer than 2 direct reportees, your individual feedback\nhas been included in your manager's analysis instead.")
                
        except Exception as e:
            self.show_no_data_message()
            QMessageBox.warning(self, "Analysis Error", f"Could not update analyses: {str(e)}")
    
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
        
        self.login_page = QWidget()
        self.setup_login_page()
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
            self.on_login_success(user[0], user[1], bool(user[2]), user[3])
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
        
        if not check_hierarchy(username):
            QMessageBox.warning(self, 'Error', 'Username not found in company hierarchy. Please contact HR.')
            return
        
        manager = get_manager(username)
        if not manager:
            QMessageBox.warning(self, 'Error', 'Could not determine your manager. Please contact HR.')
            return
        
        add_pending_user(username, password, manager)
        QMessageBox.information(
            self, 'Success', 
            'Registration submitted for approval. Your manager will review your request.'
        )
        self.stacked_widget.setCurrentIndex(0)

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
        welcome = QLabel(f'Welcome, {self.username}')
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet('font-size: 24px; font-weight: bold;')
        layout.addWidget(welcome)
        
        role = 'Superuser' if self.is_superuser else f'Manager ({self.reportee_count} reportees)' if self.reportee_count > 0 else 'Employee'
        info = QLabel(f"Manager: {self.manager if self.manager else 'None'}\nRole: {role}")
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        button_layout = QHBoxLayout()
        feedback_btn = QPushButton('Feedback Form')
        feedback_btn.setFixedHeight(80)
        feedback_btn.clicked.connect(self.open_feedback_form)
        button_layout.addWidget(feedback_btn)
        
        self.score_btn = QPushButton('Score Chart')
        self.score_btn.setFixedHeight(80)
        self.score_btn.clicked.connect(self.open_score_chart)
        button_layout.addWidget(self.score_btn)
        
        if not self.is_superuser and self.reportee_count < 2:
            self.score_btn.setEnabled(False)
            self.score_btn.setToolTip(
                f"Score chart requires 2 or more reportees. You have {self.reportee_count} reportees."
            )
        
        layout.addLayout(button_layout)
        
        if self.is_superuser or self.has_pending_approvals():
            layout.addWidget(QLabel('\nManager Actions:'))
            approval_btn = QPushButton('Review Pending Approvals')
            approval_btn.clicked.connect(self.show_approval_dialog)
            layout.addWidget(approval_btn)
        
        self.setLayout(layout)

    def show_approval_dialog(self):
        dialog = ApprovalDialog(self.username, self.is_superuser)
        dialog.exec_()
    
    def has_pending_approvals(self):
        return True  # Simplified for example
    
    def open_feedback_form(self):
        feedback_window = SurveyApp(self.username, self.manager)
        feedback_window.exec_()
    
    def open_score_chart(self):
        self.analysis_dialog = AnalysisApp(
            self.username, 
            self.manager, 
            self.is_superuser,
            self.reportee_count
        )
        self.analysis_dialog.exec_()

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

if __name__ == '__main__':
    feedback_app = FeedbackApp()
    feedback_app.run()