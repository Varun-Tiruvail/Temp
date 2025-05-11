import sys
import sqlite3
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QPushButton, 
                               QMessageBox, QTextEdit, QLabel, QMessageBox)
from PySide6.QtCore import Qt

class DatabaseResetApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Database Reset Manager")
        self.setGeometry(100, 100, 600, 400)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # Information label
        info_label = QLabel("Select Reset Type:")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info_label.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 20px;")
        
        # Buttons
        self.btn_feedback = QPushButton("Reset Feedback & Attendance Data")
        self.btn_feedback.setStyleSheet("QPushButton { background-color: #FFA500; padding: 10px; }")
        self.btn_feedback.clicked.connect(self.reset_feedback_attendance)
        
        self.btn_users = QPushButton("Reset User Accounts & Passwords")
        self.btn_users.setStyleSheet("QPushButton { background-color: #FF6347; padding: 10px; }")
        self.btn_users.clicked.connect(self.reset_user_data)
        
        self.btn_total = QPushButton("Total Reset (Full System Reset)")
        self.btn_total.setStyleSheet("QPushButton { background-color: #DC143C; padding: 10px; }")
        self.btn_total.clicked.connect(self.total_reset)
        
        # Status display
        self.status_area = QTextEdit()
        self.status_area.setReadOnly(True)
        self.status_area.setStyleSheet("background-color: #f0f0f0; padding: 10px;")
        
        layout.addWidget(info_label)
        layout.addWidget(self.btn_feedback)
        layout.addWidget(self.btn_users)
        layout.addWidget(self.btn_total)
        layout.addWidget(QLabel("Operation Log:"))
        layout.addWidget(self.status_area)
        
        self.setLayout(layout)

    def log_message(self, message):
        self.status_area.append(f"• {message}")
        
    def confirm_reset(self, message):
        reply = QMessageBox.question(
            self,
            'Confirm Reset',
            f"{message}\nThis operation cannot be undone!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        return reply == QMessageBox.StandardButton.Yes

    def reset_feedback_attendance(self):
        if not self.confirm_reset("Clear all feedback responses and attendance records?"):
            return
            
        try:
            # Reset Feedback Database
            conn = sqlite3.connect('feedback.db')
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM feedback_responses")
            conn.commit()
            conn.close()
            
            # Reset Attendance Database
            conn = sqlite3.connect('attendance.db')
            conn.execute("DELETE FROM submissions")
            conn.commit()
            conn.close()
            
            self.log_message("Successfully reset Feedback & Attendance data")
            QMessageBox.information(self, "Success", "Feedback and attendance data cleared!")
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Reset failed: {str(e)}")

    def reset_user_data(self):
        if not self.confirm_reset("Reset all user accounts and passwords?"):
            return
            
        try:
            # Reset Users in Feedback Database
            conn = sqlite3.connect('feedback.db')
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DELETE FROM users")
            conn.commit()
            conn.close()
            
            # Reset Attendance Records
            conn = sqlite3.connect('attendance.db')
            conn.execute("DELETE FROM submissions")
            conn.commit()
            conn.close()
            
            self.log_message("Successfully reset user accounts and attendance records")
            QMessageBox.information(self, "Success", "User accounts and passwords reset!")
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Reset failed: {str(e)}")

    def total_reset(self):
        if not self.confirm_reset("COMPLETELY reset ALL databases including hierarchy?"):
            return
            
        try:
            # Reset Hierarchy Database
            conn = sqlite3.connect('hierarchy.db')
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DROP TABLE IF EXISTS employees")
            conn.execute('''
                CREATE TABLE employees (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    position TEXT,
                    manager_id INTEGER,
                    FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL
                )
            ''')
            conn.commit()
            conn.close()
            
            # Reset Feedback Database
            conn = sqlite3.connect('feedback.db')
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute("DROP TABLE IF EXISTS users")
            conn.execute("DROP TABLE IF EXISTS feedback_responses")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    encrypted_data TEXT NOT NULL,
                    approved BOOLEAN NOT NULL DEFAULT 0
                )
            ''')
            conn.execute('''
                CREATE TABLE IF NOT EXISTS feedback_responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    manager TEXT NOT NULL,
                    reportee_type TEXT NOT NULL,
                    question_id TEXT,
                    response INTEGER,
                    general_feedback TEXT,
                    approval_status BOOLEAN NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            
            # Reset Attendance Database
            conn = sqlite3.connect('attendance.db')
            conn.execute("DROP TABLE IF EXISTS submissions")
            conn.execute('''
                CREATE TABLE IF NOT EXISTS submissions (
                    username TEXT PRIMARY KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            conn.close()
            
            self.log_message("Successfully performed TOTAL SYSTEM RESET")
            QMessageBox.information(self, "Success", "All databases reset to initial state!")
            
        except Exception as e:
            self.log_message(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Total reset failed: {str(e)}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = DatabaseResetApp()
    window.show()
    sys.exit(app.exec())