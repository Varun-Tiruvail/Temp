from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QPushButton, QHBoxLayout, 
    QMessageBox, QHeaderView
)
from database import get_pending_approvals, approve_user, disapprove_user

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
        
        # Title
        title = QLabel('Pending Registration Approvals')
        title.setStyleSheet('font-size: 16px; font-weight: bold;')
        layout.addWidget(title)
        
        # Table setup
        self.approval_table = QTableWidget()
        self.approval_table.setColumnCount(3)
        self.approval_table.setHorizontalHeaderLabels(['ID', 'Username', 'Manager'])
        self.approval_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.approval_table.setSelectionBehavior(QTableWidget.SelectRows)
        layout.addWidget(self.approval_table)
        
        # Buttons
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
        
        QMessageBox.information(
            self, 'Success', 
            f'Approved {len(selected)} user(s)'
        )
        self.load_pending_approvals()
    
    def disapprove_selected(self):
        selected = self.get_selected_ids()
        if not selected:
            QMessageBox.warning(self, 'Error', 'Please select at least one user')
            return
        
        reply = QMessageBox.question(
            self, 'Confirm Disapproval',
            f'Are you sure you want to disapprove {len(selected)} user(s)?\n\n'
            'This action cannot be undone.',
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for user_id in selected:
                disapprove_user(user_id)
            
            QMessageBox.information(
                self, 'Success', 
                f'Disapproved {len(selected)} user(s)'
            )
            self.load_pending_approvals()
    
    def get_selected_ids(self):
        selected_ids = []
        for item in self.approval_table.selectedItems():
            if item.column() == 0:  # Only need one item per row
                selected_ids.append(int(item.text()))
        return list(set(selected_ids))  # Remove duplicates
