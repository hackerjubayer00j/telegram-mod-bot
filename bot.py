import logging
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters
import google.generativeai as genai

# --- YOUR KEYS ---
TELEGRAM_TOKEN = "8369771657:AAF1GpWz5CjyNiTlkAcIlQGRHOduXbIBzuQ"
GOOGLE_API_KEY = "AlzaSyBFQcuryBhZsQkSKbXj8Qn23gvLVJ-vnZM"
WARNING_LIMIT = 3

# --- WEB SERVER (Keeps bot awake) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_http():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_http)
    t.start()

# --- BOT LOGIC ---
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

user_warnings = {}

async def check_message_with_ai(text):
    prompt = (
        "Classify this Telegram message: 'SAFE', 'SCAM', 'BUY_SELL', 'HARMFUL'. "
        "SCAM=crypto/phishing. BUY_SELL=selling items. HARMFUL=hate/violence. "
        f"Message: \"{text}\". Reply ONLY with the category."
    )
    try:
        response = await asyncio.to_thread(model.generate_content, prompt)
        decision = response.text.strip().upper().replace(".", "")
        valid = ["SAFE", "SCAM", "BUY_SELL", "HARMFUL"]
        for v in valid:
            if v in decision: return v
        return "SAFE"
    except:
        return "SAFE"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text or update.message.from_user.is_bot:
        return
    user = update.message.from_user
    text = update.message.text
    chat_id = update.message.chat_id

    decision = await check_message_with_ai(text)

    if decision in ["SCAM", "BUY_SELL", "HARMFUL"]:
        try: await update.message.delete()
        except: pass
        
        current_warnings = user_warnings.get(user.id, 0) + 1
        user_warnings[user.id] = current_warnings

        if current_warnings >= WARNING_LIMIT:
            try:
                await context.bot.ban_chat_member(chat_id, user.id)
                await context.bot.send_message(chat_id, f"🚫 {user.first_name} banned. Reason: {decision}")
                user_warnings.pop(user.id, None)
            except: pass
        else:
            await context.bot.send_message(chat_id, f"⚠️ Warning for {user.first_name} ({current_warnings}/{WARNING_LIMIT}). Reason: {decision}")

async def remove_warning(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    try:
        member = await chat.get_member(user.id)
        if member.status not in ['administrator', 'creator']:
            return
    except: return

    if update.message.reply_to_message:
        target_id = update.message.reply_to_message.from_user.id
        if target_id in user_warnings:
            user_warnings[target_id] -= 1
            await update.message.reply_text("✅ Warning removed.")
        else:
            await update.message.reply_text("User has no warnings.")

if __name__ == '__main__':
    keep_alive()
    app_bot = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app_bot.add_handler(CommandHandler("unwarn", remove_warning))
    app_bot.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app_bot.run_polling()
