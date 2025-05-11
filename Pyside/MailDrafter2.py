import pandas as pd
import sqlite3
import win32com.client as win32
from datetime import datetime

class FeedbackReminder:
    def __init__(self, excel_path):
        self.excel_data = pd.read_excel(excel_path)
        self.shared_mailbox = "shared@company.com"  # Update with your shared mailbox
        self.manager_email = "manager@company.com"  # Update with manager email
        self.unregistered = []
        self.not_submitted = []

    def check_compliance(self):
        # Connect to databases
        hier_conn = sqlite3.connect('hierarchy.db')
        fb_conn = sqlite3.connect('feedback.db')
        att_conn = sqlite3.connect('attendance.db')

        for _, row in self.excel_data.iterrows():
            name = row['Name']
            email = row['Email']

            # Check if in hierarchy
            if not hier_conn.execute("SELECT 1 FROM employees WHERE name = ?", (name,)).fetchone():
                continue

            # Check registration
            is_registered = fb_conn.execute("SELECT 1 FROM users WHERE username = ?", (name,)).fetchone()
            has_submitted = att_conn.execute("SELECT 1 FROM submissions WHERE username = ?", (name,)).fetchone()

            if not is_registered:
                self.unregistered.append(email)
            elif not has_submitted:
                self.not_submitted.append(email)

        hier_conn.close()
        fb_conn.close()
        att_conn.close()

    def create_drafts(self):
        outlook = win32.Dispatch('Outlook.Application')
        
        # Create draft for unregistered users
        if self.unregistered:
            mail = outlook.CreateItem(0)
            mail._oleobj_.Invoke(*(64209, 0, 8, 0, win32.Dispatch("Outlook.Application").Session.Accounts.Item(self.shared_mailbox)))
            mail.Subject = f"Urgent: Complete Your Registration for Feedback System ({datetime.today().strftime('%d/%m/%Y')})"
            mail.HTMLBody = f"""
                <p>Dear Colleagues,</p>
                <p>Our records show you haven't registered for the feedback system yet...</p>
                <p>Registration Link: [INSERT LINK HERE]</p>
                <p>Best regards,<br/>
                {self.manager_email}</p>
            """
            mail.BCC = ";".join(self.unregistered)
            mail.Save()

        # Create draft for pending submissions
        if self.not_submitted:
            mail = outlook.CreateItem(0)
            mail._oleobj_.Invoke(*(64209, 0, 8, 0, win32.Dispatch("Outlook.Application").Session.Accounts.Item(self.shared_mailbox)))
            mail.Subject = f"Reminder: Complete Pending Feedback Submission ({datetime.today().strftime('%d/%m/%Y')})"
            mail.HTMLBody = f"""
                <p>Dear Team Members,</p>
                <p>This is a reminder to complete your mandatory feedback submission...</p>
                <p>Submission Link: [INSERT LINK HERE]</p>
                <p>Best regards,<br/>
                {self.manager_email}</p>
            """
            mail.BCC = ";".join(self.not_submitted)
            mail.Save()

if __name__ == "__main__":
    # Usage
    reminder = FeedbackReminder("employees.xlsx")
    reminder.check_compliance()
    reminder.create_drafts()
    print("Drafts created in Outlook with BCC recipients from shared mailbox")