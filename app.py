from flask import Flask, request
import requests
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import os
import re

app = Flask(__name__)
print("✅ Flask server started")

# Zoho credentials
CLIENT_ID = "1000.OT73L88OF6C9PO1SS47SD0BE97ZJEB"
CLIENT_SECRET = "a5c2eb75f9fdb5ec968f745881ef305386c1b263a6"
REFRESH_TOKEN = "1000.c228b6cbdf8c0e94061a85407d52ca12.4d2994982a44af2bb44ecab60ab9838b"

# Twilio credentials
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# In-memory stores
user_sessions = {}
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
            # Fetch Zoho contact and save data
            access_token = get_access_token()
            if access_token:
                contacts = get_contacts_for_phone(access_token, sender)
                if contacts:
                    first = contacts[0]
                    name = first.get("Full_Name") or first.get("Last_Name") or "Unknown"
                    user_data_store[phone_key] = {
                        "name": name,
                        "number": sender
                    }
            else:
                user_data_store[phone_key] = {
                    "name": "Unknown",
                    "number": sender
                }

            user_sessions[phone_key] = "AWAITING_OPTION"
            resp.message(
                "Welcome! Please select an option by replying with the number:\n"
                "1. My Data\n2. Full Data"
            )
            return str(resp)
        else:
            resp.message("Please say 'Hi' to start the service.")
            return str(resp)

    elif state == "AWAITING_OPTION":
        if incoming_msg == "1":
            access_token = get_access_token()
            contacts = get_contacts_for_phone(access_token, sender) if access_token else []
            if contacts:
                lines = []
                for c in contacts[:10]:
                    name = c.get("Full_Name") or c.get("Last_Name") or "No Name"
                    email = c.get("Email") or "No Email"
                    number = sender.replace("whatsapp:", "")
                    lines.append(f"{name} - {email} - {number}")
                resp.message("Your Data:\n" + "\n".join(lines))
            else:
                saved = user_data_store.get(phone_key)
                if saved:
                    resp.message(f"Your saved data:\nName: {saved.get('name')}\nNumber: {saved.get('number')}")
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
                lines = []
                for c in contact_list[:10]:
                    name = c.get("Full_Name") or c.get("Last_Name") or "No Name"
                    email = c.get("Email") or "No Email"
                    lines.append(f"{name} - {email}")
                if len(contact_list) > 10:
                    lines.append(f"...and {len(contact_list) - 10} more contacts.")
                resp.message("Full Data:\n" + "\n".join(lines))
            else:
                resp.message("No contacts found or error retrieving data.")

            user_sessions[phone_key] = "START"
            return str(resp)

        else:
            resp.message("Invalid option. Please reply with 1 or 2.")
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
