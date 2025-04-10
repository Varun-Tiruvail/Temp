from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QStackedWidget, QComboBox
)
from PyQt5.QtCore import Qt
from database import (
    check_hierarchy, get_manager, add_pending_user, 
    validate_login, initialize_databases
)

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
        
        # Login Page
        self.login_page = QWidget()
        self.setup_login_page()
        
        # Register Page
        self.register_page = QWidget()
        self.setup_register_page()
        
        self.stacked_widget.addWidget(self.login_page)
        self.stacked_widget.addWidget(self.register_page)
        
        layout = QVBoxLayout()
        layout.addWidget(self.stacked_widget)
        self.setLayout(layout)
    
    def setup_login_page(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel('Login')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        
        # Username
        layout.addWidget(QLabel('Username:'))
        self.login_username = QLineEdit()
        layout.addWidget(self.login_username)
        
        # Password
        layout.addWidget(QLabel('Password:'))
        self.login_password = QLineEdit()
        self.login_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.login_password)
        
        # Login Button
        login_btn = QPushButton('Login')
        login_btn.clicked.connect(self.handle_login)
        layout.addWidget(login_btn)
        
        # Switch to Register
        switch_btn = QPushButton('Need an account? Register')
        switch_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        layout.addWidget(switch_btn)
        
        self.login_page.setLayout(layout)
    
    def setup_register_page(self):
        layout = QVBoxLayout()
        
        # Title
        title = QLabel('Register')
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet('font-size: 20px; font-weight: bold;')
        layout.addWidget(title)
        
        # Username
        layout.addWidget(QLabel('Username:'))
        self.register_username = QLineEdit()
        layout.addWidget(self.register_username)
        
        # Password
        layout.addWidget(QLabel('Password:'))
        self.register_password = QLineEdit()
        self.register_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.register_password)
        
        # Confirm Password
        layout.addWidget(QLabel('Confirm Password:'))
        self.register_confirm_password = QLineEdit()
        self.register_confirm_password.setEchoMode(QLineEdit.Password)
        layout.addWidget(self.register_confirm_password)
        
        # Register Button
        register_btn = QPushButton('Register')
        register_btn.clicked.connect(self.handle_register)
        layout.addWidget(register_btn)
        
        # Switch to Login
        switch_btn = QPushButton('Already have an account? Login')
        switch_btn.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        layout.addWidget(switch_btn)
        
        self.register_page.setLayout(layout)
    
    # def handle_login(self):
    #     username = self.login_username.text().strip()
    #     password = self.login_password.text().strip()
        
    #     if not username or not password:
    #         QMessageBox.warning(self, 'Error', 'Please enter both username and password')
    #         return
        
    #     user = validate_login(username, password)
    #     if user:
    #         self.on_login_success(user[0], user[1], bool(user[2]))
    #     else:
    #         QMessageBox.warning(self, 'Error', 'Invalid username or password')

    def handle_login(self):
        username = self.login_username.text().strip()
        password = self.login_password.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, 'Error', 'Please enter both username and password')
            return
        
        user_info = validate_login(username, password)
        if user_info:
            username, manager, is_superuser, reportee_count = user_info
            self.on_login_success(username, manager, is_superuser, reportee_count)
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
            QMessageBox.warning(
                self, 'Error', 
                'Username not found in company hierarchy. Please contact HR.'
            )
            return
        
        manager = get_manager(username)
        if not manager:
            QMessageBox.warning(
                self, 'Error', 
                'Could not determine your manager. Please contact HR.'
            )
            return
        
        add_pending_user(username, password, manager)
        QMessageBox.information(
            self, 'Success', 
            'Registration submitted for approval. Your manager will review your request.'
        )
        self.stacked_widget.setCurrentIndex(0)
    
    # In your auth system (auth_window.py or similar)
    def authenticate_user(username, password):
        # This is a placeholder - implement your actual authentication
        user_data = {
            'username': username,
            'manager': 'Manager Name',  # Get from DB
            'is_superuser': False,      # Get from DB
            'reportee_count': 3         # Get from DB - count of direct reportees
        }
        return user_data