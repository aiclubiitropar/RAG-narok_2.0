import os
import imaplib
import email
from email.header import decode_header
from dotenv import load_dotenv

load_dotenv('.env')
username = os.getenv('GMAIL_USERNAME')
password = os.getenv('GMAIL_PASSWORD')

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(username, password)
mail.select('inbox')

status, messages = mail.search(None, '(SUBJECT "mess" SUBJECT "menu")')
email_ids = messages[0].split()

if email_ids:
    e_id = email_ids[-1]
    print("Latest Email ID:", e_id)
    status, msg_data = mail.fetch(e_id, "(RFC822)")
    for response_part in msg_data:
        if isinstance(response_part, tuple):
            msg = email.message_from_bytes(response_part[1])
            subject, encoding = decode_header(msg.get("Subject", ""))[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else "utf-8")
            print("Subject:", subject)
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition"))
                    filename = part.get_filename()
                    print(f"Part: {content_type} | Disposition: {content_disposition} | Filename: {filename}")
else:
    print("No emails found")
