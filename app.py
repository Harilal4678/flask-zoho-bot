from flask import Flask, request
import requests
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
import json

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

def get_all_documents(access_token):
    # Using Leads as a placeholder
    url = "https://www.zohoapis.in/crm/v2/Leads"
    headers = {"Authorization": f"Zoho-oauthtoken {access_token}"}
    resp = requests.get(url, headers=headers)
    if resp.status_code == 200:
        print("✅ Leads fetched (as placeholder for documents)")
        leads = resp.json().get("data", [])
        for lead in leads:
            name = lead.get("Full_Name") or lead.get("Last_Name") or "No Name"
            email = lead.get("Email", "No Email")
            print(f"- {name} | {email}")
    else:
        print(f"❌ Error fetching leads: {resp.text}")

@app.route('/webhook', methods=['POST'])
def webhook():
    sender = request.values.get('From', '')  # e.g. 'whatsapp:+919876543210'
    incoming_msg = request.values.get('Body', '').strip().lower()

    print(f"\n📩 Incoming from {sender}: {incoming_msg}")

    resp = MessagingResponse()

    if incoming_msg in ['hi', 'hello', 'hey']:
        resp.message(
            "Hello! What service do you need? Please reply with the number:\n"
            "1. Life Insurance\n2. Health Insurance\n3. Car Insurance"
        )
        print("✅ Twilio response sent successfully")
        return str(resp)

    if incoming_msg in ['1', '2', '3']:
        access_token = get_access_token()
        if not access_token:
            resp.message("Sorry, there was an error connecting to CRM. Please try again later.")
            print("✅ Twilio response sent successfully (CRM error fallback)")
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

            resp.message("Contacts data:\n" + "\n".join(message_lines))
        else:
            resp.message("No contacts found or error retrieving data.")

        print("✅ Twilio response sent successfully (contacts)")
        return str(resp)

    resp.message("Sorry, I didn't understand that. Please reply with 'Hi' to start.")
    print("✅ Twilio response sent successfully (fallback)")
    return str(resp)

if __name__ == "__main__":
    access_token = get_access_token()
    if access_token:
        get_all_documents(access_token)
    else:
        print("❌ Failed to fetch documents at startup due to access token issue.")
    app.run(port=5000)
