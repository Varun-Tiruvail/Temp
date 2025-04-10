from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton, 
    QMessageBox, QHBoxLayout
)
from PyQt5.QtCore import Qt
from approval_dialog import ApprovalDialog
from Survey_App import SurveyApp
class Dashboard(QWidget):
    def __init__(self, username, manager, is_superuser):
        super().__init__()
        self.username = username
        self.manager = manager
        self.is_superuser = is_superuser
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
        info = QLabel(
            f"Manager: {self.manager if self.manager else 'Superuser'}\n"
            f"Role: {'Superuser' if self.is_superuser else 'Employee'}"
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
        
        # Score Chart Button
        score_btn = QPushButton('Score Chart')
        score_btn.setFixedHeight(80)
        score_btn.clicked.connect(self.open_score_chart)
        button_layout.addWidget(score_btn)
        
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
        # In a real app, you would check the database
        # For this example, we'll assume managers always have pending approvals
        return True
    
    # def show_approval_dialog(self):
    #     dialog = ApprovalDialog(self.username)
    #     dialog.exec_()
    def open_feedback_form(self):
        feedback_window = SurveyApp(self.username, self.manager)
        feedback_window.show()
    # def open_feedback_form(self):
    #     QMessageBox.information(
    #         self, 'Info', 
    #         'This would open the feedback form. You can replace this with your own implementation.'
    #     )
        # In your implementation:
        # import feedback_form
        # self.feedback_window = feedback_form.FeedbackWindow()
        # self.feedback_window.show()
    
    def open_score_chart(self):
        QMessageBox.information(
            self, 'Info', 
            'This would open the score chart. You can replace this with your own implementation.'
        )
        # In your implementation:
        # import score_chart
        # self.score_window = score_chart.ScoreWindow()
        # self.score_window.show()