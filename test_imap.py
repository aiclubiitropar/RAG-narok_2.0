import os
import imaplib
from dotenv import load_dotenv

load_dotenv('.env')
username = os.getenv('GMAIL_USERNAME')
password = os.getenv('GMAIL_PASSWORD')

mail = imaplib.IMAP4_SSL('imap.gmail.com')
mail.login(username, password)
mail.select('inbox')

print('Test 1:', mail.search(None, 'SUBJECT', '"mess"', 'SUBJECT', '"menu"'))
try:
    print('Test 2:', mail.search(None, '(SUBJECT "mess" SUBJECT "menu")'))
except Exception as e:
    print('Test 2 failed:', e)
print('Test 3:', mail.search(None, 'X-GM-RAW', '"subject:(mess menu) has:attachment"'))
