from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
import os
import json
from dotenv import load_dotenv

from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM
import torch

# Load environment variables
load_dotenv()

app = FastAPI()

# === Config ===
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")

# === System Prompt (defines bot behavior) ===
SYSTEM_PROMPT = """
You are the official TPL Trakker Auto-Reg WhatsApp Bot.

You help field technicians quickly check vehicle installation status and tracker details.

Key guidelines:
- Always respond professionally, clearly, and concisely in English.
- Be friendly and patient.
- Your main goal is to get the vehicle registration number (e.g., ABC-123) or Job ID from the technician.
- If they send a plate or job ID, acknowledge it and say you're checking.
- If they ask about battery tamper, accelerometer, wiring type, etc., confirm you're retrieving live status.
- If the message is unclear or a greeting, politely guide them to send the vehicle reg or job ID.
- Never share fake data — just confirm you're searching or checking.

Examples:
User: Hi → "Hello! Please send the vehicle registration (e.g., ABC-123) or Job ID to check status."
User: ABC-123 → "Searching for vehicle ABC-123... One moment please."
User: Job 5678 battery tamper? → "Checking Job 5678 — retrieving pass status and battery tamper info..."
User: Is pass issued for KAR-456? → "Let me check vehicle KAR-456 for you. One moment..."
"""

# === Load Model ONCE at startup (Vercel cold start) ===
print("Loading flan-t5-base model with 8-bit quantization...")

tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
model = AutoModelForSeq2SeqLM.from_pretrained(
    "google/flan-t5-base",
    device_map="auto",          # Uses CPU automatically
    load_in_8bit=True,          # Reduces memory ~50%
    torch_dtype=torch.float16   # Further optimization
)

generator = pipeline(
    "text2text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=128,
    temperature=0.7,
    do_sample=True
)

print("Model loaded successfully!")

# === Generate Response ===
def generate_response(user_message: str) -> str:
    prompt = f"{SYSTEM_PROMPT}\n\nTechnician message: \"{user_message}\"\nBot response:"

    try:
        result = generator(prompt)
        reply = result[0]["generated_text"]

        # Clean output (remove echoed prompt if present)
        if "Bot response:" in reply:
            reply = reply.split("Bot response:", 1)[1].strip()

        if not reply.strip():
            reply = "One moment please while I process your request."

        return reply

    except Exception as e:
        print("Model inference error:", str(e))
        return "Sorry, I'm having a technical issue right now. Please try again in a minute."


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
        print("Sent:", r.status_code, r.json())
    except Exception as e:
        print("Send failed:", e)


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
    print("Incoming:", json.dumps(data, indent=2))

    try:
        entry = data["entry"][0]["changes"][0]["value"]
        if "messages" not in entry:
            return {"status": "ok"}

        msg = entry["messages"][0]
        sender = msg["from"]
        user_text = msg["text"]["body"].strip()

        reply = generate_response(user_text)
        send_message(sender, reply)

    except Exception as e:
        print("Error:", e)

    return {"status": "ok"}


# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)