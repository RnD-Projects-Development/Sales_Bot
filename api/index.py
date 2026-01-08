# api/index.py (Vercel) and main.py (local) — Identical

from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse, JSONResponse
import requests
import os
import json
from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

app = FastAPI()

# === Config ===
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

# Preferred model — fast, powerful, great for professional assistant
GROQ_MODEL = "llama-3.3-70b-versatile"  # You can change to "mixtral-8x7b-32768" or "gemma2-9b-it" later

# === System Prompt - Defines Bot Behavior (Phase 1 Ready) ===
SYSTEM_PROMPT = """
You are the official TPL Trakker Auto-Reg WhatsApp Bot.

You assist field technicians by helping them quickly verify installation status and tracker details.

Key Guidelines:
- Always respond professionally, clearly, and concisely in English.
- Be friendly and patient.
- Your primary goal is to obtain the vehicle registration number (e.g., ABC-123, KAR-456) or Job ID (e.g., 5678).
- If a vehicle reg or job ID is provided, acknowledge it and confirm you're checking.
- If they mention battery tamper, accelerometer, wiring type, or any device parameter, confirm you're retrieving live status.
- If the message is a greeting or unclear, politely ask for the vehicle registration or Job ID.
- NEVER invent or display fake data — only confirm actions like "searching" or "checking".
- Use emojis sparingly for better readability (e.g., 🔍, ✅, ⏳).

Examples:
- User: Hi → Hello! Please send the vehicle registration (e.g., ABC-123) or Job ID to check status.
- User: ABC-123 → 🔍 Searching for vehicle ABC-123... One moment please.
- User: job 5678 battery tamper → ✅ Checking Job 5678 — retrieving pass status and battery tamper info...
"""

# === Generate Response Using Groq ===
def generate_response(user_message: str) -> str:
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ],
            model=GROQ_MODEL,
            temperature=0.6,
            max_tokens=150,
            top_p=0.9
        )
        return chat_completion.choices[0].message.content.strip()

    except Exception as e:
        print("Groq API Error:", str(e))
        return "I'm having a temporary issue connecting. Please try again in a moment."


# === Send WhatsApp Message ===
def send_message(to: str, text: str):
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text}
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=10)
        print("WhatsApp Send:", r.status_code, r.json())
    except Exception as e:
        print("Failed to send message:", e)


# === Webhook Verification ===
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge")
):
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    return PlainTextResponse("Verification failed", status_code=403)


# === Receive Messages ===
@app.post("/webhook")
async def receive_message(request: Request):
    data = await request.json()
    print("Incoming webhook:", json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "ok"}

        msg = entry["messages"][0]
        sender = msg["from"]
        user_text = msg["text"]["body"].strip()

        # Generate smart reply using Groq
        reply = generate_response(user_text)

        # Send reply
        send_message(sender, reply)

    except Exception as e:
        print("Error processing message:", e)

    return {"status": "ok"}


# For local testing with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)