from flask import Flask, request
import requests
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
import re

app = Flask(__name__)
print("✅ Flask server started")

# Zoho credentials (keep your values here)
CLIENT_ID = "1000.OT73L88OF6C9PO1SS47SD0BE97ZJEB"
CLIENT_SECRET = "a5c2eb75f9fdb5ec968f745881ef305386c1b263a6"
REFRESH_TOKEN = "1000.c228b6cbdf8c0e94061a85407d52ca12.4d2994982a44af2bb44ecab60ab9838b"

# Twilio credentials - replace with your real Twilio credentials or env vars
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Simple in-memory user session store: phone -> state
user_sessions = {}
# Simple in-memory user saved data: phone -> {"name": str}
user_data_store = {}

@app.route('/')
def health():
    return "✅ Flask app is running", 200

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
        print("✅ Zoho access token fetched")
        return resp.json().get("access_token")
    else:
        print(f"❌ Zoho token error: {resp.text}")
        return None

def get_all_contacts(access_token):
    url = "https://www.zohoapis.in/crm/v2/Contacts"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        print("✅ Zoho contacts fetched")
        return resp.json()
    else:
        print(f"❌ Zoho contacts error: {resp.text}")
        return None

def get_contacts_for_phone(access_token, phone):
    all_contacts = get_all_contacts(access_token)
    if not all_contacts or "data" not in all_contacts:
        return []

    matched = []
    for contact in all_contacts["data"]:
        phones = []
        for key in ["Phone", "Mobile", "Home_Phone", "Other_Phone"]:
            val = contact.get(key)
            if val:
                phones.append(val)

        normalized_phones = [re.sub(r'\D', '', p) for p in phones]
        normalized_user_phone = re.sub(r'\D', '', phone)

        if any(normalized_user_phone.endswith(p[-10:]) for p in normalized_phones):
            matched.append(contact)
        if len(matched) >= 10:
            break
    return matched

def create_contact_in_zoho(access_token, name, phone):
    url = "https://www.zohoapis.in/crm/v2/Contacts"
    headers = {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }
    data = {
        "data": [
            {
                "Last_Name": name or "New User",
                "Mobile": phone
            }
        ]
    }
    resp = requests.post(url, headers=headers, json=data)
    if resp.status_code in [200, 201, 202]:
        print(f"✅ New contact created for {phone}")
    else:
        print(f"❌ Failed to create contact: {resp.text}")

@app.route('/webhook', methods=['POST'])
def webhook():
    sender = request.values.get('From', '')  # e.g. 'whatsapp:+919876543210'
    incoming_msg = request.values.get('Body', '').strip()
    phone_key = sender.lower()
    print(f"\n📩 Incoming from {sender}: {incoming_msg}")
    resp = MessagingResponse()
    state = user_sessions.get(phone_key, "START")

    if state == "START":
        if incoming_msg.lower() in ['hi', 'hello', 'hey']:
            access_token = get_access_token()
            if access_token:
                existing = get_contacts_for_phone(access_token, sender)
                if not existing:
                    # Save number in Zoho CRM as new contact
                    create_contact_in_zoho(access_token, "WhatsApp User", sender)
            user_sessions[phone_key] = "AWAITING_OPTION"
            resp.message(
                "Welcome! Please select an option by replying with the number:\n"
                "1. My Data\n2. Full Data\n3. Save My Data"
            )
            return str(resp)
        else:
            resp.message("Please say 'Hi' to start the service.")
            return str(resp)

    elif state == "AWAITING_OPTION":
        if incoming_msg == "1":
            access_token = get_access_token()
            if not access_token:
                resp.message("Sorry, error connecting to CRM. Please try later.")
                user_sessions[phone_key] = "START"
                return str(resp)

            contacts = get_contacts_for_phone(access_token, sender)
            if contacts:
                message_lines = []
                for c in contacts[:10]:
                    name = c.get("Full_Name") or c.get("Last_Name") or "No Name"
                    email = c.get("Email") or "No Email"
                    number = c.get("Mobile") or c.get("Phone") or "No Number"
                    message_lines.append(f"{name} - {email} - 📱 {number}")
                resp.message("Your Data:\n" + "\n".join(message_lines))
            else:
                saved = user_data_store.get(phone_key)
                if saved and saved.get("name"):
                    resp.message(f"Your saved data:\nName: {saved['name']}\nNumber: {sender}")
                else:
                    resp.message("No contact data found for your number and no saved data.")
            user_sessions[phone_key] = "START"
            return str(resp)

        elif incoming_msg == "2":
            access_token = get_access_token()
            if not access_token:
                resp.message("Sorry, error connecting to CRM. Please try later.")
                user_sessions[phone_key] = "START"
                return str(resp)

            contacts_data = get_all_contacts(access_token)
            if contacts_data and "data" in contacts_data:
                contact_list = contacts_data["data"]
                message_lines = []
                for c in contact_list[:10]:
                    name = c.get("Full_Name") or c.get("Last_Name") or "No Name"
                    email = c.get("Email") or "No Email"
                    message_lines.append(f"{name} - {email}")
                if len(contact_list) > 10:
                    message_lines.append(f"...and {len(contact_list) - 10} more contacts.")
                resp.message("Full Data:\n" + "\n".join(message_lines))
            else:
                resp.message("No contacts found or error retrieving data.")
            user_sessions[phone_key] = "START"
            return str(resp)

        elif incoming_msg == "3":
            user_sessions[phone_key] = "AWAITING_NAME"
            resp.message("Please enter your full name:")
            return str(resp)

        else:
            resp.message("Invalid option. Please reply with 1, 2, or 3.")
            return str(resp)

    elif state == "AWAITING_NAME":
        if re.match(r"^[A-Za-z ]{2,50}$", incoming_msg):
            user_data_store[phone_key] = {"name": incoming_msg.strip()}
            user_sessions[phone_key] = "START"
            resp.message(f"Thanks {incoming_msg}! Your data has been saved.")
        else:
            resp.message("Invalid name format. Please enter your full name using only letters and spaces.")
        return str(resp)

    else:
        user_sessions[phone_key] = "START"
        resp.message("Session reset. Please say 'Hi' to start again.")
        return str(resp)

if __name__ == "__main__":
    access_token = get_access_token()
    if access_token:
        pass
    else:
        print("❌ Failed to fetch documents at startup due to access token issue.")
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
