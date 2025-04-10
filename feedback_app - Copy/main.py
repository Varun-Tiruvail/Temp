import sys
from PyQt5.QtWidgets import QApplication
from auth_window import AuthWindow
from dashboard import Dashboard

class FeedbackApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.auth_window = AuthWindow(self.on_login_success)
        self.auth_window.show()
    
    def on_login_success(self, username, manager, is_superuser):
        self.auth_window.close()
        self.dashboard = Dashboard(username, manager, is_superuser)
        self.dashboard.show()
    
    def run(self):
        sys.exit(self.app.exec_())

if __name__ == '__main__':
    feedback_app = FeedbackApp()
    feedback_app.run()