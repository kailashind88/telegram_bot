import os
import json
import logging
from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set!")

DEFAULT_LANG = "hinglish"
MEMORY_FILE = "memory.json"

groq_client = Groq(api_key=GROQ_API_KEY)
user_lang_map = {}

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f, indent=2)

memory_store = load_memory()

def ask_ai(user_message, lang, history=None):
    if history is None:
        history = []
    try:
        if lang == "hinglish":
            messages = [{"role": "system", "content": "You are a friendly assistant for people from Himachal Pradesh. Always reply in simple Hinglish. Short and conversational."}]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            response = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=messages)
            return response.choices[0].message.content
        else:
            hindi_messages = [{"role": "system", "content": "You are a helpful assistant. Always reply in simple Hindi. Keep reply short."}]
            hindi_messages.extend(history)
            hindi_messages.append({"role": "user", "content": user_message})
            hindi_response = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=hindi_messages)
            hindi_text = hindi_response.choices[0].message.content

            dialect_map = {
                "pahari": "Translate Hindi text into General Himachali Pahari. Use Devanagari. Sound like local Himachali speaking casually.",
                "kangri": "Translate Hindi text into Kangri dialect (Kangra region). Use Devanagari. Casual local tone.",
                "mandyali": "Translate Hindi text into Mandyali dialect (Mandi region). Use Devanagari. Friendly local tone."
            }
            instruction = dialect_map.get(lang, dialect_map["pahari"])
            pahari_messages = [{"role": "system", "content": "You are an expert translator. " + instruction + " Only output translated text. No explanation. No English."}]
            pahari_messages.append({"role": "user", "content": hindi_text})
            pahari_response = groq_client.chat.completions.create(model="llama-3.3-70b-versatile", messages=pahari_messages)
            return pahari_response.choices[0].message.content
    except Exception as e:
        logging.error("AI error: " + str(e))
        return "Maaf kariye, thodi dikkat aa rahi hai. Thodi der baad phir koshish karein."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang_map[update.effective_user.id] = DEFAULT_LANG
    await update.message.reply_text("Han G Maraj! Aaun Tusa Ra AI assistant aa")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Choose Language:\n/set_hinglish\n/set_pahari\n/set_kangri\n/set_mandyali")

async def set_hinglish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang_map[update.effective_user.id] = "hinglish"
    await update.message.reply_text("Language set to Hinglish")

async def set_pahari(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang_map[update.effective_user.id] = "pahari"
    await update.message.reply_text("Language set to General Pahari")

async def set_kangri(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang_map[update.effective_user.id] = "kangri"
    await update.message.reply_text("Language set to Kangri")

async def set_mandyali(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_lang_map[update.effective_user.id] = "mandyali"
    await update.message.reply_text("Language set to Mandyali")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    memory_store[user_id] = []
    save_memory(memory_store)
    await update.message.reply_text("Memory reset ho gayi hai!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    user_text = update.message.text
    lang = user_lang_map.get(update.effective_user.id, DEFAULT_LANG)

    if user_id not in memory_store:
        memory_store[user_id] = []

    history = memory_store[user_id][-10:]
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = ask_ai(user_text, lang, history)
    memory_store[user_id].append({"role": "user", "content": user_text})
    memory_store[user_id].append({"role": "assistant", "content": reply})
    save_memory(memory_store)
    await update.message.reply_text(reply)

def main():
    print("Bot starting...")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("set_hinglish", set_hinglish))
    app.add_handler(CommandHandler("set_pahari", set_pahari))
    app.add_handler(CommandHandler("set_kangri", set_kangri))
    app.add_handler(CommandHandler("set_mandyali", set_mandyali))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
