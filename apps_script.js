/**
 * RAGnarok 2.0 - Serverless Webhook Worker (Google Apps Script)
 * 
 * Instructions:
 * 1. Go to https://script.google.com/ and create a new project.
 * 2. Paste this entire file into Code.gs.
 * 3. Replace 'YOUR_ADMIN_PASSWORD_HERE' with your actual backend admin password.
 * 4. IMPORTANT: Click "Deploy" -> "New Deployment" -> Select "Web App".
 *    - Execute as: "Me"
 *    - Who has access: "Anyone"
 *    - Click "Deploy", authorize the app, and COPY the Web App URL.
 * 5. Paste the Web App URL into your Hugging Face Space .env file as:
 *    APPS_SCRIPT_WEBHOOK_URL="https://script.google.com/macros/s/.../exec"
 * 6. Set up a Time-Driven Trigger (clock icon) to run `runAllScrapers` daily!
 */

const HF_MESS_MENU_URL = "https://iotacluster-rag-narok-backend.hf.space/api/admin/worker/upload-base64-pdf";
const HF_EMAILS_URL = "https://iotacluster-rag-narok-backend.hf.space/api/admin/worker/upload-emails";

const ADMIN_PASSWORD = "123456789";

/**
 * Web App Endpoint: This allows your Command Center's "Trigger Now" 
 * button to send an HTTP GET request to Google to instantly run the scrapers!
 */
function doGet(e) {
  Logger.log("Received GET request from Command Center. Starting scrapers...");
  runAllScrapers();
  return ContentService.createTextOutput(JSON.stringify({
    "status": "success",
    "message": "Scrapers executed successfully."
  })).setMimeType(ContentService.MimeType.JSON);
}

function runAllScrapers() {
  pushUnreadEmailsToHuggingFace();
  pushMessMenuToHuggingFace();
}

function pushUnreadEmailsToHuggingFace() {
  Logger.log("Scanning for general unread emails...");

  // Search for up to 5 unread emails that are NOT Mess Menus
  const threads = GmailApp.search('is:unread -subject:"Mess Menu"', 0, 5);

  if (threads.length === 0) {
    Logger.log("No new unread general emails found.");
    return;
  }

  let emailsPayload = [];
  const blocklist = ["no-reply@accounts.google.com", "security alert", "unstop", "linkedin", "kaggle", "team unstop", "canva", "noreply@github.com", "noreply", "feed", "huggingface", "instagram", "udacity", "udemy", "supabase", "vercel"];

  for (let i = 0; i < threads.length; i++) {
    let messages = threads[i].getMessages();
    let message = messages[messages.length - 1]; // Get latest message in thread

    let subject = message.getSubject() || "";
    let sender = message.getFrom() || "";
    let date = message.getDate().toISOString();
    let body = message.getPlainBody() || "";

    // Check blocklist
    let isBlocked = false;
    let senderAndSub = (sender + " " + subject).toLowerCase();
    for (let b of blocklist) {
      if (senderAndSub.includes(b)) {
        isBlocked = true;
        break;
      }
    }

    if (!isBlocked && body.trim() !== "") {
      emailsPayload.push({
        "id": message.getId(),
        "subject": subject,
        "sender": sender,
        "date": date,
        "body": body
      });
      Logger.log("Prepared to send: " + subject);
    }

    // Mark as read so we don't process it again tomorrow
    message.markRead();
  }

  if (emailsPayload.length === 0) {
    Logger.log("No valid non-blocklisted emails found.");
    return;
  }

  const payload = {
    "emails": emailsPayload
  };

  const options = {
    "method": "post",
    "contentType": "application/json",
    "headers": {
      "Authorization": "Bearer " + ADMIN_PASSWORD
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };

  Logger.log("Pushing " + emailsPayload.length + " emails to Hugging Face...");
  const response = UrlFetchApp.fetch(HF_EMAILS_URL, options);

  Logger.log("Response Code: " + response.getResponseCode());
  Logger.log("Response Body: " + response.getContentText());
}

function pushMessMenuToHuggingFace() {
  Logger.log("Scanning for Mess Menu PDF...");
  const threads = GmailApp.search('subject:"Mess Menu" has:attachment', 0, 1);

  if (threads.length === 0) {
    Logger.log("No Mess Menu emails found.");
    return;
  }

  const messages = threads[0].getMessages();
  const latestMessage = messages[messages.length - 1];

  const attachments = latestMessage.getAttachments();
  let pdfAttachment = null;

  for (let i = 0; i < attachments.length; i++) {
    if (attachments[i].getContentType() === "application/pdf" || attachments[i].getName().toLowerCase().endsWith(".pdf")) {
      pdfAttachment = attachments[i];
      break;
    }
  }

  if (!pdfAttachment) {
    Logger.log("Found Mess Menu email, but no PDF attachment was found.");
    return;
  }

  Logger.log("Found PDF: " + pdfAttachment.getName());

  const pdfBytes = pdfAttachment.getBytes();
  const base64Data = Utilities.base64Encode(pdfBytes);

  const payload = {
    "filename": pdfAttachment.getName(),
    "base64_data": base64Data
  };

  const options = {
    "method": "post",
    "contentType": "application/json",
    "headers": {
      "Authorization": "Bearer " + ADMIN_PASSWORD
    },
    "payload": JSON.stringify(payload),
    "muteHttpExceptions": true
  };

  Logger.log("Pushing to Hugging Face webhook...");
  const response = UrlFetchApp.fetch(HF_MESS_MENU_URL, options);

  Logger.log("Response Code: " + response.getResponseCode());
  Logger.log("Response Body: " + response.getContentText());
}
