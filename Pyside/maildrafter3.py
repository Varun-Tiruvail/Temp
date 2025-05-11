import sys
import sqlite3
import pandas as pd
import win32com.client as win32
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QLabel, QFileDialog, QMessageBox, 
                               QTextEdit, QLineEdit, QTableWidget, QTableWidgetItem)
from PySide6.QtCore import Qt

class EmailDraftApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Feedback Compliance Mail Drafter")
        self.setGeometry(100, 100, 1000, 800)
        self.excel_data = None
        self.results = {'unregistered': [], 'not_submitted': []}
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # File selection
        self.file_btn = QPushButton("Load Employee Excel File")
        self.file_btn.clicked.connect(self.load_excel)
        self.file_label = QLabel("No file loaded")
        
        # Configuration inputs
        config_layout = QHBoxLayout()
        self.shared_mail_input = QLineEdit()
        self.shared_mail_input.setPlaceholderText("Shared Mailbox Address")
        self.manager_mail_input = QLineEdit()
        self.manager_mail_input.setPlaceholderText("Manager Signature Email")
        config_layout.addWidget(QLabel("Shared Mailbox:"))
        config_layout.addWidget(self.shared_mail_input)
        config_layout.addWidget(QLabel("Manager Email:"))
        config_layout.addWidget(self.manager_mail_input)

        # Email templates
        self.reg_template = QTextEdit()
        self.reg_template.setPlainText(
            "Subject: Registration Required for Feedback System\n\n"
            "Dear {name},\n\nOur records show you haven't registered..."
        )
        self.remind_template = QTextEdit()
        self.remind_template.setPlainText(
            "Subject: Feedback Submission Reminder\n\n"
            "Dear {name},\n\nPlease submit your feedback..."
        )

        # Results display
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(3)
        self.results_table.setHorizontalHeaderLabels(["Name", "Email", "Status"])
        
        # Buttons
        btn_analyze = QPushButton("Analyze Compliance")
        btn_analyze.clicked.connect(self.analyze_compliance)
        btn_draft = QPushButton("Create Outlook Drafts")
        btn_draft.clicked.connect(self.create_drafts)

        # Layout organization
        layout.addWidget(self.file_btn)
        layout.addWidget(self.file_label)
        layout.addLayout(config_layout)
        
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Registration Template:"))
        template_layout.addWidget(QLabel("Reminder Template:"))
        
        template_edit_layout = QHBoxLayout()
        template_edit_layout.addWidget(self.reg_template)
        template_edit_layout.addWidget(self.remind_template)

        layout.addLayout(template_layout)
        layout.addLayout(template_edit_layout)
        layout.addWidget(QLabel("Compliance Results:"))
        layout.addWidget(self.results_table)
        layout.addWidget(btn_analyze)
        layout.addWidget(btn_draft)

    def load_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if path:
            try:
                self.excel_data = pd.read_excel(path)
                self.file_label.setText(f"Loaded: {path.split('/')[-1]}")
                self.results_table.setRowCount(0)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def analyze_compliance(self):
        if self.excel_data is None:
            QMessageBox.warning(self, "Warning", "Please load an Excel file first")
            return

        required_columns = ['Name', 'Email']
        if not all(col in self.excel_data.columns for col in required_columns):
            QMessageBox.critical(self, "Error", "Excel file must contain 'Name' and 'Email' columns")
            return

        self.results = {'unregistered': [], 'not_submitted': []}
        self.results_table.setRowCount(0)

        try:
            hier_conn = sqlite3.connect('hierarchy.db')
            fb_conn = sqlite3.connect('feedback.db')
            att_conn = sqlite3.connect('attendance.db')

            for _, row in self.excel_data.iterrows():
                name = row['Name']
                email = row['Email']

                # Check hierarchy
                if not hier_conn.execute("SELECT 1 FROM employees WHERE name = ?", (name,)).fetchone():
                    continue

                # Check registration
                registered = fb_conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone()
                submitted = att_conn.execute("SELECT 1 FROM submissions WHERE username = ?", (name,)).fetchone()

                status = ""
                if not registered:
                    self.results['unregistered'].append((name, email))
                    status = "Unregistered"
                elif not submitted:
                    self.results['not_submitted'].append((name, email))
                    status = "Pending Submission"
                else:
                    continue

                # Add to table
                row_pos = self.results_table.rowCount()
                self.results_table.insertRow(row_pos)
                self.results_table.setItem(row_pos, 0, QTableWidgetItem(name))
                self.results_table.setItem(row_pos, 1, QTableWidgetItem(email))
                status_item = QTableWidgetItem(status)
                status_item.setBackground(Qt.yellow if status == "Unregistered" else Qt.red)
                self.results_table.setItem(row_pos, 2, status_item)

            QMessageBox.information(self, "Analysis Complete", 
                                  f"Found:\n"
                                  f"- Unregistered: {len(self.results['unregistered'])}\n"
                                  f"- Pending Submission: {len(self.results['not_submitted'])}")

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
        finally:
            hier_conn.close()
            fb_conn.close()
            att_conn.close()

    def create_drafts(self):
        if not self.results['unregistered'] and not self.results['not_submitted']:
            QMessageBox.warning(self, "Warning", "No recipients to email")
            return

        try:
            outlook = win32.Dispatch('Outlook.Application')
            
            # Create registration draft
            if self.results['unregistered']:
                self.create_draft(
                    outlook=outlook,
                    recipients=[email for _, email in self.results['unregistered']],
                    subject=self.reg_template.toPlainText().split('\n')[0].replace('Subject: ', ''),
                    body='\n'.join(self.reg_template.toPlainText().split('\n')[2:]),
                    category="registration"
                )

            # Create reminder draft
            if self.results['not_submitted']:
                self.create_draft(
                    outlook=outlook,
                    recipients=[email for _, email in self.results['not_submitted']],
                    subject=self.remind_template.toPlainText().split('\n')[0].replace('Subject: ', ''),
                    body='\n'.join(self.remind_template.toPlainText().split('\n')[2:]),
                    category="reminder"
                )

            QMessageBox.information(self, "Success", "Drafts created in Outlook!")

        except Exception as e:
            QMessageBox.critical(self, "Outlook Error", f"Failed to create drafts: {str(e)}")

    def create_draft(self, outlook, recipients, subject, body, category):
        mail = outlook.CreateItem(0)
        
        # Set shared mailbox sender
        try:
            mail._oleobj_.Invoke(*(64209, 0, 8, 0, outlook.Session.Accounts.Item(
                self.shared_mail_input.text())))
        except Exception as e:
            QMessageBox.warning(self, "Sender Error", 
                              f"Could not set shared mailbox sender: {str(e)}\nUsing default account.")

        mail.Subject = subject
        mail.BCC = ";".join(recipients)
        mail.Body = body.replace('{name}', 'Colleague').replace(
            '{manager}', self.manager_mail_input.text())
        
        # Add classification tag
        mail.UserProperties.Add("EmailType", 1).Value = category
        mail.Save()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EmailDraftApp()
    window.show()
    sys.exit(app.exec())