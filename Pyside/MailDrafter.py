import sys
import sqlite3
import pandas as pd
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QPushButton, QTableWidget, QTableWidgetItem, QLabel, 
                               QFileDialog, QMessageBox, QTextEdit)
from PySide6.QtCore import Qt

class FeedbackReminderTool(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Feedback Compliance Manager")
        self.setGeometry(100, 100, 1000, 800)
        self.email_template_reg = """
            Subject: Registration Required for Feedback System
            
            Dear {name},
            
            Our records show you haven't yet registered for the employee feedback system.
            Please register at [registration link] using your company credentials.
            
            Regards,
            HR Team
        """
        self.email_template_remind = """
            Subject: Reminder: Pending Feedback Submission
            
            Dear {name},
            
            We notice you haven't submitted your feedback yet. Please complete it by [deadline].
            
            Submit here: [feedback link]
            
            Regards,
            HR Team
        """
        self.init_ui()
        self.data = pd.DataFrame()
        self.results = {}

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        # File selection
        self.file_label = QLabel("No file selected")
        btn_load = QPushButton("Load Excel File")
        btn_load.clicked.connect(self.load_excel)
        
        # Results display
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Email", "Status", "Actions"])
        
        # Email templates
        self.template_editor_reg = QTextEdit(self.email_template_reg)
        self.template_editor_remind = QTextEdit(self.email_template_remind)
        
        # Buttons
        btn_analyze = QPushButton("Analyze Compliance")
        btn_analyze.clicked.connect(self.analyze_compliance)
        btn_export = QPushButton("Export All Emails")
        btn_export.clicked.connect(self.export_emails)

        # Layout organization
        file_layout = QHBoxLayout()
        file_layout.addWidget(btn_load)
        file_layout.addWidget(self.file_label)
        
        template_layout = QHBoxLayout()
        template_layout.addWidget(QLabel("Registration Email Template:"))
        template_layout.addWidget(QLabel("Reminder Email Template:"))
        
        template_edit_layout = QHBoxLayout()
        template_edit_layout.addWidget(self.template_editor_reg)
        template_edit_layout.addWidget(self.template_editor_remind)

        layout.addLayout(file_layout)
        layout.addWidget(btn_analyze)
        layout.addWidget(self.table)
        layout.addLayout(template_layout)
        layout.addLayout(template_edit_layout)
        layout.addWidget(btn_export)

    def load_excel(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open Excel File", "", "Excel Files (*.xlsx *.xls)")
        if file_path:
            try:
                self.data = pd.read_excel(file_path)
                self.file_label.setText(f"Loaded: {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def analyze_compliance(self):
        if self.data.empty:
            QMessageBox.warning(self, "Warning", "Please load an Excel file first")
            return

        required_columns = ['Name', 'Email']
        if not all(col in self.data.columns for col in required_columns):
            QMessageBox.critical(self, "Error", "Excel file must contain 'Name' and 'Email' columns")
            return

        self.results = {'not_registered': [], 'registered_not_submitted': [], 'submitted': []}

        try:
            # Database connections
            hier_conn = sqlite3.connect('hierarchy.db')
            feedback_conn = sqlite3.connect('feedback.db')
            attend_conn = sqlite3.connect('attendance.db')

            for _, row in self.data.iterrows():
                name = row['Name']
                email = row['Email']

                # Check if in hierarchy
                hier_cur = hier_conn.cursor()
                hier_cur.execute("SELECT name FROM employees WHERE name = ?", (name,))
                if not hier_cur.fetchone():
                    continue  # Skip if not in hierarchy

                # Check registration
                feedback_cur = feedback_conn.cursor()
                feedback_cur.execute("SELECT username FROM users WHERE username = ?", (name,))
                if not feedback_cur.fetchone():
                    self.results['not_registered'].append(row)
                    continue

                # Check submission
                attend_cur = attend_conn.cursor()
                attend_cur.execute("SELECT username FROM submissions WHERE username = ?", (name,))
                if not attend_cur.fetchone():
                    self.results['registered_not_submitted'].append(row)
                else:
                    self.results['submitted'].append(row)

            self.update_table()
            QMessageBox.information(self, "Analysis Complete", 
                                  f"Results:\n"
                                  f"- Not Registered: {len(self.results['not_registered'])}\n"
                                  f"- Registered but Not Submitted: {len(self.results['registered_not_submitted'])}\n"
                                  f"- Submitted: {len(self.results['submitted'])}")

        except sqlite3.Error as e:
            QMessageBox.critical(self, "Database Error", str(e))
        finally:
            hier_conn.close()
            feedback_conn.close()
            attend_conn.close()

    def update_table(self):
        self.table.setRowCount(0)
        row_count = sum(len(v) for v in self.results.values())
        self.table.setRowCount(row_count)
        
        row_index = 0
        for category in ['not_registered', 'registered_not_submitted', 'submitted']:
            for record in self.results[category]:
                self.table.setItem(row_index, 0, QTableWidgetItem(record['Name']))
                self.table.setItem(row_index, 1, QTableWidgetItem(record['Email']))
                status_item = QTableWidgetItem(category.replace('_', ' ').title())
                
                # Color coding
                if category == 'not_registered':
                    status_item.setBackground(Qt.GlobalColor.yellow)
                elif category == 'registered_not_submitted':
                    status_item.setBackground(Qt.GlobalColor.red)
                else:
                    status_item.setBackground(Qt.GlobalColor.green)
                
                self.table.setItem(row_index, 2, status_item)
                
                # Preview button
                preview_btn = QPushButton("Preview Email")
                preview_btn.clicked.connect(lambda _, r=record, c=category: self.preview_email(r, c))
                self.table.setCellWidget(row_index, 3, preview_btn)
                row_index += 1

    def preview_email(self, record, category):
        email_body = ""
        if category == 'not_registered':
            email_body = self.template_editor_reg.toPlainText().format(name=record['Name'])
        else:
            email_body = self.template_editor_remind.toPlainText().format(name=record['Name'])
        
        preview_dialog = QMessageBox(self)
        preview_dialog.setWindowTitle("Email Preview")
        preview_dialog.setText(f"To: {record['Email']}\n\n{email_body}")
        preview_dialog.exec()

    def export_emails(self):
        if not any(len(v) > 0 for v in self.results.values()):
            QMessageBox.warning(self, "Warning", "No results to export")
            return

        try:
            output = []
            for category, records in self.results.items():
                if not records:
                    continue
                
                for record in records:
                    if category == 'not_registered':
                        body = self.template_editor_reg.toPlainText().format(name=record['Name'])
                    elif category == 'registered_not_submitted':
                        body = self.template_editor_remind.toPlainText().format(name=record['Name'])
                    else:
                        continue
                    
                    output.append({
                        'email': record['Email'],
                        'subject': body.split('\n')[0].replace('Subject: ', ''),
                        'body': '\n'.join(body.split('\n')[1:]).strip()
                    })

            df = pd.DataFrame(output)
            save_path, _ = QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
            if save_path:
                df.to_csv(save_path, index=False)
                QMessageBox.information(self, "Success", f"Exported {len(df)} emails to {save_path}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error", str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = FeedbackReminderTool()
    window.show()
    sys.exit(app.exec())