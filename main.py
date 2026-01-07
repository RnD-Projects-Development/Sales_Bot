from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
import requests
import os
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

app = FastAPI()

# Use either .env or hardcode — do not do both
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")  # e.g., "my_verify_token"
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")  # your long access token
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")  # e.g., "928961663632928"

# 🔹 Webhook verification (Meta calls this once)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# 🔹 Receive messages
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Incoming:", data)

    try:
        msg = data["entry"][0]["changes"][0]["value"]["messages"][0]
        sender = msg["from"]
        text = msg["text"]["body"]

        send_message(sender, f"You said: {text}")
    except KeyError:
        pass  # No message found

    return {"status": "ok"}

# 🔹 Send WhatsApp reply
def send_message(to, text):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    r = requests.post(url, json=payload, headers=headers)
    print("Sent message:", r.json())
