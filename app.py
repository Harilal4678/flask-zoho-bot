from flask import Flask, request
import requests
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import re
import os


app = Flask(__name__)

# Zoho OAuth credentials
CLIENT_ID = "1000.OT73L88OF6C9PO1SS47SD0BE97ZJEB"
CLIENT_SECRET = "a5c2eb75f9fdb5ec968f745881ef305386c1b263a6"
REFRESH_TOKEN = "1000.c228b6cbdf8c0e94061a85407d52ca12.4d2994982a44af2bb44ecab60ab9838b"

# Twilio credentials
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"

# Initialize Twilio client
try:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print("✅ Connected to Twilio")
except Exception as e:
    print("❌ Twilio connection failed:", e)

def get_access_token():
    url = "https://accounts.zoho.in/oauth/v2/token"
    params = {
        "refresh_token": REFRESH_TOKEN,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token"
    }
    resp = requests.post(url, params=params)
    if resp.status_code == 200:
        print("✅ Connected to Zoho CRM")
        return resp.json().get("access_token")
    else:
        print("❌ Failed to get Zoho token:", resp.text)
        return None

def create_contact(access_token, name, phone):
    # Clean name and phone
    name = ' '.join(word.capitalize() for word in name.strip().split())
    last_name = name.split()[-1]
    phone = phone.strip().zfill(10)

    url = "https://www.zohoapis.in/crm/v2/Contacts"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "data": [
            {
                "Last_Name": last_name,
                "Full_Name": name,
                "Phone": phone
            }
        ]
    }
    response = requests.post(url, headers=headers, json=payload)
    if response.status_code in [200, 201] and "data" in response.json():
        print(f"✅ Saved contact: {name} ({phone})")
        return True
    else:
        print("❌ Failed to save contact:", response.text)
        return False

def fetch_all_contacts(access_token):
    url = "https://www.zohoapis.in/crm/v2/Contacts"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        print("✅ Accessed 10 contacts from Zoho")
        contacts = response.json().get("data", [])
        result = []
        for contact in contacts[:10]:
            name = contact.get("Full_Name") or contact.get("Last_Name", "Unknown")
            phone = contact.get("Phone", "No Phone")
            result.append(f"{name} - {phone}")
        return result
    else:
        print("❌ Error fetching contacts:", response.text)
        return None

def fetch_my_data(access_token, phone):
    phone = phone[-10:]
    url = f"https://www.zohoapis.in/crm/v2/Contacts/search?phone={phone}"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200 and "data" in response.json():
        contact = response.json()["data"][0]
        name = contact.get("Full_Name") or contact.get("Last_Name", "Unknown")
        phone = contact.get("Phone", "No Phone")
        return f"👤 Your Data:\nName: {name}\nPhone: {phone}"
    else:
        return "❌ Your contact was not found in CRM."

@app.route('/webhook', methods=['POST'])
def webhook():
    sender = request.values.get('From', '')  # e.g., whatsapp:+91XXXXXXXXXX
    phone_from = re.sub(r'\D', '', sender)[-10:]
    incoming_msg = request.values.get('Body', '').strip()
    resp = MessagingResponse()

    # Handle "hi" or greetings
    if incoming_msg.lower() in ['hi', 'hello', 'hey', 'menu']:
        access_token = get_access_token()
        if access_token:
            auto_name = f"User_{phone_from}"
            create_contact(access_token, auto_name, phone_from)
        resp.message(
            "👋 Welcome! Choose an option:\n"
            "1️⃣ My Data\n"
            "2️⃣ Full Data\n"
            "3️⃣ Save My Data (format: Name: Your Name, Phone: Your Number)"
        )
        return str(resp)

    # Option 1: My Data
    if incoming_msg == '1':
        access_token = get_access_token()
        if not access_token:
            resp.message("❌ Zoho CRM access failed.")
            return str(resp)
        result = fetch_my_data(access_token, phone_from)
        resp.message(result)
        return str(resp)

    # Option 2: Full Data (first 10)
    if incoming_msg == '2':
        access_token = get_access_token()
        if not access_token:
            resp.message("❌ Zoho CRM access failed.")
            return str(resp)
        contacts = fetch_all_contacts(access_token)
        if contacts:
            resp.message("📋 First 10 Contacts:\n" + "\n".join(contacts))
        else:
            resp.message("❌ No contacts found.")
        return str(resp)

    # Option 3: Save contact manually
    match = re.search(r'name\s*[:\-]\s*([a-zA-Z\s]+)[,]?\s*phone\s*[:\-]?\s*(\d{7,15})', incoming_msg, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        phone = match.group(2).strip()
        access_token = get_access_token()
        if not access_token:
            resp.message("❌ Zoho CRM access failed.")
            return str(resp)
        if create_contact(access_token, name, phone):
            resp.message(f"✅ Contact saved: {name} ({phone.zfill(10)})")
        else:
            resp.message("❌ Failed to save contact.")
        return str(resp)

    # Fallback
    resp.message(
        "❓ I didn’t understand that.\n"
        "Send 'Hi' to start.\n"
        "Send: Name: Your Name, Phone: Your Number to save your contact."
    )
    return str(resp)


if __name__ == "__main__":
    access_token = get_access_token()
    if access_token:
        pass
    else:
        print("❌ Failed to fetch documents at startup due to access token issue.")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)