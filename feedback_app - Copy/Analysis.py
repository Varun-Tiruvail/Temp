import sys
import os
import glob
import sqlite3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QComboBox, QTabWidget, QPushButton,
                           QFileDialog, QMessageBox, QScrollArea, QGroupBox,
                           QGridLayout, QSplitter)
from PyQt5.QtCore import Qt
import matplotlib
from matplotlib import cm
from PyQt5.QtGui import QFont
matplotlib.use('Qt5Agg')  # Set the backend to Qt5Agg

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
    axes.set_facecolor('#f9f9f9')  # Light background
    axes.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.7)  # Add gridlines
    axes.set_title(title, fontsize=14, fontweight='bold', color='#333333')  # Title styling
    if xlabel:
        axes.set_xlabel(xlabel, fontsize=12, color='#333333')
    if ylabel:
        axes.set_ylabel(ylabel, fontsize=12, color='#333333')
    axes.tick_params(axis='both', which='major', labelsize=10, colors='#333333')  # Tick styling

# Fix: Use proper inheritance to ensure the canvas is a QWidget
class MatplotlibCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = plt.figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.fig = fig  # Store the figure as an instance variable
        
        # Create an annotation object that we'll use for hover labels
        self.annot = self.axes.annotate("", xy=(0,0), xytext=(20,20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                       arrowprops=dict(arrowstyle="->"))
        self.annot.set_visible(False)
        
        # Connect event handlers for hover
        self.fig.canvas.mpl_connect("motion_notify_event", self.hover)
        
    def hover(self, event):
        if not event.inaxes:
            return
        
        # Check if we have wedges (for pie charts)
        wedges = getattr(self, 'pie_wedges', None)
        labels = getattr(self, 'pie_labels', None)
        
        if not wedges or not labels:
            return
            
        # Check if cursor is over a wedge
        for i, wedge in enumerate(wedges):
            if wedge.contains_point([event.x, event.y]):
                # Make annotation visible
                self.annot.set_visible(True)
                # Set annotation text
                self.annot.set_text(labels[i])
                # Get wedge center
                theta = np.pi/2 - (wedge.theta1 + wedge.theta2)/2
                r = wedge.r/2
                x = r * np.cos(theta)
                y = r * np.sin(theta)
                # Update annotation position
                self.annot.xy = (x, y)
                # Redraw
                self.draw_idle()
                return
                
        # If not over any wedge, hide annotation
        self.annot.set_visible(False)
        self.draw_idle()

class AnalysisApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Survey Analysis Dashboard")
        self.resize(1000, 800)
        
        # Load question definitions for reference
        try:
            self.questions_df = pd.read_excel('survey_questions.xlsx')
            
            # Check for required columns and map them if they have different names
            required_columns = ['QuestionID', 'Category', 'Question', 
                              'Option1', 'Option2', 'Option3', 'Option4']
            
            # Map of expected column names to potential alternatives
            column_alternatives = {
                'QuestionID': ['QuestionID', 'Question_ID', 'Id', 'ID'],
                'Category': ['Category', 'Section', 'Type'],
                'Question': ['Question', 'QuestionText', 'Text'],
                'Option1': ['Option1', 'Option_1', 'Choice1'],
                'Option2': ['Option2', 'Option_2', 'Choice2'],
                'Option3': ['Option3', 'Option_3', 'Choice3'],
                'Option4': ['Option4', 'Option_4', 'Choice4']
            }
            
            # Check and rename columns if needed
            actual_columns = self.questions_df.columns.tolist()
            for expected, alternatives in column_alternatives.items():
                if expected not in actual_columns:
                    # Try to find an alternative
                    for alt in alternatives:
                        if alt in actual_columns:
                            self.questions_df.rename(columns={alt: expected}, inplace=True)
                            print(f"Renamed column '{alt}' to '{expected}'")
                            break
            
            # Verify all required columns exist
            missing_columns = [col for col in required_columns if col not in self.questions_df.columns]
            if missing_columns:
                raise KeyError(f"Missing required columns: {', '.join(missing_columns)}")
                
        except FileNotFoundError:
            QMessageBox.critical(self, "Error", "survey_questions.xlsx file not found! Please run the question generator first.")
            sys.exit(1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading questions file: {str(e)}")
            sys.exit(1)
            
        self.merged_data = None
        self.responses_df = None
        
        # Create main layout
        main_layout = QVBoxLayout()
        
        # Controls area
        controls_layout = QHBoxLayout()
        
        self.load_button = QPushButton("Load Survey Data")
        style_buttons(self.load_button)
        self.load_button.clicked.connect(self.load_survey_data)
        
        controls_layout.addWidget(self.load_button)
        controls_layout.addStretch(1)
        
        # Analysis tabs
        self.tabs = QTabWidget()
        
        # Create the three analysis views
        self.create_overall_tab()
        self.create_section_tab()
        self.create_question_tab()
        
        main_layout.addLayout(controls_layout)
        main_layout.addWidget(self.tabs)
        
        self.setLayout(main_layout)
    
    def create_overall_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        
        # Create a canvas and add it to the layout
        self.overall_canvas = MatplotlibCanvas(width=8, height=6)
        layout.addWidget(self.overall_canvas)
        
        # Add a help label to explain the hover functionality
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
        
        # Create a canvas and add it to the layout
        self.section_canvas = MatplotlibCanvas(width=8, height=6)
        
        layout.addLayout(section_controls)
        layout.addWidget(self.section_canvas)
        
        # Add a help label to explain the hover functionality
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
        
        # Create a canvas and add it to the layout
        self.question_canvas = MatplotlibCanvas(width=8, height=6)
        
        layout.addLayout(question_controls)
        layout.addWidget(self.question_canvas)
        
        # Add a help label to explain the hover functionality
        help_label = QLabel("Hover over pie slices to see option details")
        help_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_label)
        
        container.setLayout(layout)
        tab.setWidget(container)
        self.tabs.addTab(tab, "Question Analysis")
        
        # Initialize the question list
        self.update_question_list("Cultural")
    
    def update_question_list(self, category):
        self.question_combo.clear()
        
        category_questions = self.questions_df[self.questions_df['Category'] == category]
        for _, row in category_questions.iterrows():
            self.question_combo.addItem(row['Question'], row['QuestionID'])
    
    def load_survey_data(self):
        # Let user select multiple DB files
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Survey Database Files", "", "SQLite Files (*.db)"
        )
        
        if not files:
            return
        
        # Merge data from all selected files
        all_responses = []
        all_users = []
        
        for file in files:
            try:
                conn = sqlite3.connect(file)
                
                # Get responses
                responses_df = pd.read_sql_query("SELECT * FROM responses", conn)
                responses_df['db_file'] = os.path.basename(file)
                all_responses.append(responses_df)
                
                # Get user info
                user_df = pd.read_sql_query("SELECT * FROM user_info", conn)
                user_df['db_file'] = os.path.basename(file)
                all_users.append(user_df)
                
                conn.close()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Could not load data from {file}: {str(e)}")
        
        if not all_responses or not all_users:
            QMessageBox.warning(self, "No Data", "No valid data found in selected files.")
            return
        
        try:
            # Combine all data
            self.responses_df = pd.concat(all_responses)
            self.users_df = pd.concat(all_users)
            
            # Merge with question definitions
            self.merged_data = pd.merge(
                self.responses_df,
                self.questions_df,
                left_on='question_id',
                right_on='QuestionID'
            )
            
            # Update all analyses
            self.update_overall_analysis()
            self.update_section_analysis(self.section_combo.currentText())
            self.update_question_analysis(self.question_combo.currentText())
            
            QMessageBox.information(
                self, "Data Loaded", 
                f"Successfully loaded data from {len(files)} survey files.\n"
                f"Total responses: {len(self.users_df)}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error processing data: {str(e)}")
    
    def update_overall_analysis(self):
        if self.merged_data is None:
            return

        try:
            # Clear the canvas
            self.overall_canvas.axes.clear()

            # Calculate average scores by category
            category_scores = self.merged_data.groupby('Category')['response'].mean()

            # Create bar chart with a modern color palette
            colors = cm.viridis(np.linspace(0.2, 0.8, len(category_scores)))
            bars = self.overall_canvas.axes.bar(category_scores.index, category_scores.values, color=colors)

            # Beautify the chart
            beautify_charts(self.overall_canvas.axes, 'Overall Category Scores', ylabel='Average Score (1-4)')
            self.overall_canvas.axes.set_ylim(0, 4)

            # Add value labels on top of bars
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
            # Clear the canvas
            self.section_canvas.axes.clear()
            
            # Filter for selected category
            category_data = self.merged_data[self.merged_data['Category'] == category]
            
            if category_data.empty:
                self.section_canvas.axes.text(0.5, 0.5, f"No data for {category} category",
                                            ha='center', va='center')
                self.section_canvas.draw()
                return
            
            # Calculate average scores by question
            question_scores = category_data.groupby(['QuestionID', 'Question'])['response'].mean()
            
            # Create bar chart
            questions = [q[1] for q in question_scores.index]
            shortened_questions = [q[:20] + '...' if len(q) > 20 else q for q in questions]
            
            # beautify_charts(self.section_canvas.axes, 'Overall Section Scores', ylabel='Average Score (1-4)')
            colors = cm.viridis(np.linspace(0.2, 0.8, len(question_scores)))
            bars = self.section_canvas.axes.bar(range(len(shortened_questions)), question_scores.values)
            beautify_charts(self.section_canvas.axes, 'Overall Section Scores', ylabel='Average Score (1-4)')
            
            
            # Add labels
            self.section_canvas.axes.set_ylabel('Average Score (1-4)')
            self.section_canvas.axes.set_title(f'{category} Category - Question Scores')
            self.section_canvas.axes.set_ylim(0, 4)
            self.section_canvas.axes.set_xticks(range(len(shortened_questions)))
            self.section_canvas.axes.set_xticklabels(shortened_questions, rotation=45, ha='right')
            
            # Store the full questions for hover labels
            self.section_canvas.bar_labels = questions
            self.section_canvas.bars = bars
            
            # Make annotation for hover
            self.section_canvas.annot = self.section_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
                                       textcoords="offset points",
                                       bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                       arrowprops=dict(arrowstyle="->"))
            self.section_canvas.annot.set_visible(False)
            
            # Modify hover function for bars
            # Modify the hover function for bars
            def hover(event):
                if not event.inaxes:
                    return

                for i, bar in enumerate(bars):
                    if bar.contains_point([event.x, event.y]):  # Remove [0] indexing
                        # Make annotation visible
                        self.section_canvas.annot.set_visible(True)
                        # Set annotation text with full question text and score
                        self.section_canvas.annot.set_text(f"{questions[i]}\nScore: {question_scores.values[i]:.2f}")
                        # Update annotation position
                        self.section_canvas.annot.xy = (bar.get_x() + bar.get_width() / 2, bar.get_height())
                        # Redraw
                        self.section_canvas.draw_idle()
                        return

                # If not over any bar, hide annotation
                self.section_canvas.annot.set_visible(False)
                self.section_canvas.draw_idle()
            
            # Connect hover function
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
            # Get question ID from combo box
            question_id = self.question_combo.currentData()
            
            # Clear the canvas
            self.question_canvas.axes.clear()
            
            # Filter for selected question
            question_data = self.merged_data[self.merged_data['QuestionID'] == question_id]
            
            if question_data.empty:
                self.question_canvas.axes.text(0.5, 0.5, "No data for this question",
                                             ha='center', va='center')
                self.question_canvas.draw()
                return
            
            # Count responses for each option
            option_counts = question_data['response'].value_counts().sort_index()
            
            # Get option labels
            option_labels = []
            for i in range(1, 5):
                col_name = f'Option{i}'
                option_text = question_data[col_name].iloc[0] if not question_data.empty else f"Option {i}"
                option_labels.append(f"{i}: {option_text}")
            
            # Create values for all options (1-4), even if some have zero responses
            all_options = pd.Series([0, 0, 0, 0], index=[1, 2, 3, 4])
            for idx, count in option_counts.items():
                if idx > 0 and idx <= 4:  # Exclude -1 (unanswered) and invalid responses
                    all_options[idx] = count
            
            if all_options.sum() == 0:
                self.question_canvas.axes.text(0.5, 0.5, "No responses for this question",
                                             ha='center', va='center')
                self.question_canvas.draw()
            else:
                # Create pie chart with no labels initially
                wedges, _ = self.question_canvas.axes.pie(
                    all_options, 
                    labels=None,  # No labels initially
                    autopct=None,  # No percentage labels
                    startangle=90,
                    explode=[0.05, 0.05, 0.05, 0.05],  # Slight explosion for all pieces
                    shadow=True,  # Add shadow for better visibility
                    wedgeprops={'linewidth': 1, 'edgecolor': 'white'}  # Add white edge for better visibility
                )
                
                # Store the wedges and labels for hover functionality
                self.question_canvas.pie_wedges = wedges
                
                # Create detailed labels with count and percentage
                total = all_options.sum()
                detailed_labels = []
                for i, (label, count) in enumerate(zip(option_labels, all_options)):
                    percentage = (count / total) * 100 if total > 0 else 0
                    detailed_labels.append(f"{label}\nCount: {count}\n({percentage:.1f}%)")
                
                self.question_canvas.pie_labels = detailed_labels
                
                # Add a title and legend
                self.question_canvas.axes.set_title(f'Response Distribution: {question_text}')
                self.question_canvas.axes.legend(wedges, option_labels, title="Options", 
                                               loc="center left", bbox_to_anchor=(1, 0, 0.5, 1))
                
                self.question_canvas.axes.axis('equal')  # Equal aspect ratio ensures pie is circular
                
                # Make annotation for hover
                self.question_canvas.annot = self.question_canvas.axes.annotate("", xy=(0,0), xytext=(20,20),
                                           textcoords="offset points",
                                           bbox=dict(boxstyle="round", fc="white", alpha=0.8),
                                           arrowprops=dict(arrowstyle="->"))
                self.question_canvas.annot.set_visible(False)
                
                # Adjust layout to make room for the legend
                self.question_canvas.fig.tight_layout()
                
            self.question_canvas.draw()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error updating question analysis: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AnalysisApp()
    window.show()
    sys.exit(app.exec())