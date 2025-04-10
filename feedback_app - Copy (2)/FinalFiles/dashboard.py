from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QMessageBox, QHBoxLayout, QApplication
)
from PyQt5.QtCore import Qt
from approval_dialog import ApprovalDialog
from Survey_App import SurveyApp
from database import count_reportees

class Dashboard(QWidget):
    def __init__(self, username, manager, is_superuser, reportee_count=0):
        super().__init__()
        self.username = username
        self.manager = manager
        self.is_superuser = is_superuser
        # Count reportees from hierarchy file if user is a manager
        # if reportee_count == 0:
        self.reportee_count = count_reportees(username) if not is_superuser else 0
        # self.reportee_count = count_reportees(username) if not is_superuser else 0
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('Employee Feedback System - Dashboard')
        self.setFixedSize(600, 400)
        
        layout = QVBoxLayout()
        
        # Welcome message
        welcome = QLabel(f'Welcome, {self.username}')
        welcome.setAlignment(Qt.AlignCenter)
        welcome.setStyleSheet('font-size: 24px; font-weight: bold;')
        layout.addWidget(welcome)
        
        # User info
        role = 'Superuser' if self.is_superuser else f'Manager ({self.reportee_count} reportees)' if self.reportee_count > 0 else 'Employee'
        info = QLabel(
            f"Manager: {self.manager if self.manager else 'None'}\n"
            f"Role: {role}"
        )
        info.setAlignment(Qt.AlignCenter)
        layout.addWidget(info)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        # Feedback Form Button
        feedback_btn = QPushButton('Feedback Form')
        feedback_btn.setFixedHeight(80)
        feedback_btn.clicked.connect(self.open_feedback_form)
        button_layout.addWidget(feedback_btn)
        
        # Score Chart Button (only enabled if allowed)
        self.score_btn = QPushButton('Score Chart')
        self.score_btn.setFixedHeight(80)
        self.score_btn.clicked.connect(self.open_score_chart)
        button_layout.addWidget(self.score_btn)
        
        # Disable score chart if not allowed
        MIN_REPORTEES_FOR_SCORECHART = 2
        if not self.is_superuser and self.reportee_count < MIN_REPORTEES_FOR_SCORECHART:
            self.score_btn.setEnabled(False)
            self.score_btn.setToolTip(
                f"Score chart requires {MIN_REPORTEES_FOR_SCORECHART} or more reportees. "
                f"You have {self.reportee_count}."
            )
        
        layout.addLayout(button_layout)
        
        # Manager-specific buttons
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
        #Required for SQL Server
        # In a real app, you would check the database
        # For this example, we'll assume managers always have pending approvals
        return True
    
    def open_feedback_form(self):
        feedback_window = SurveyApp(self.username, self.manager)
        feedback_window.show()
    
    def open_score_chart(self):
        from analysis_app import AnalysisApp
        self.analysis_dialog = AnalysisApp(
            self.username, 
            self.manager, 
            self.is_superuser,
            self.reportee_count
        )
        self.analysis_dialog.exec_()