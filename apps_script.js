/**
 * RAGnarok Mess Menu Webhook
 * 
 * Instructions:
 * 1. Go to https://script.google.com/ and create a new project.
 * 2. Paste this entire file into Code.gs.
 * 3. Replace 'YOUR_ADMIN_PASSWORD_HERE' with your actual backend admin password.
 * 4. Run the `pushMessMenuToHuggingFace` function to test it.
 * 5. Set up a Time-Driven Trigger (clock icon on the left) to run this function daily!
 */

const HF_WEBHOOK_URL = "https://iotacluster-rag-narok-backend.hf.space/api/admin/worker/upload-base64-pdf";
const ADMIN_PASSWORD = "YOUR_ADMIN_PASSWORD_HERE"; // Put your ADMIN_PASSWORD from .env here

function pushMessMenuToHuggingFace() {
  // Search for the latest email with "Mess Menu" that has an attachment
  const threads = GmailApp.search('subject:"Mess Menu" has:attachment', 0, 1);
  
  if (threads.length === 0) {
    Logger.log("No Mess Menu emails found.");
    return;
  }
  
  const messages = threads[0].getMessages();
  // Get the most recent message in the thread
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
  
  // Get the raw bytes and convert to base64
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
  const response = UrlFetchApp.fetch(HF_WEBHOOK_URL, options);
  
  Logger.log("Response Code: " + response.getResponseCode());
  Logger.log("Response Body: " + response.getContentText());
}
