import os
import json
import logging
from groq import Groq
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
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

def get_hindi_answer(user_message, history=None):
    if history is None:
        history = []
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant. Always reply in simple Hindi (Devanagari script). Keep reply short and conversational."
        }
    ]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages
    )
    return response.choices[0].message.content

def translate_to_pahari(hindi_text, dialect):
    dialect_instructions = {
        "pahari": "Translate Hindi text into General Himachali Pahari. Use Devanagari. Sound like local Himachali speaking casually.",
        "kangri": "Translate Hindi text into Kangri dialect (Kangra region). Use Devanagari. Casual local tone.",
        "mandyali": "Translate Hindi text into Mandyali dialect (Mandi region). Use Devanagari. Friendly local tone."
    }
    instruction = dialect_instructions.get(dialect, dialect_instructions["pahari"])
    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": "You are an expert translator. " + instruction + " IMPORTANT: Only output translated text. No explanation. No English. Keep friendly tone."
            },
            {
                "role": "user",
                "content": hindi_text
            }
        ]
    )
    return response.choices[0].message.content

def ask_ai(user_message, lang, history=None):
    if history is None:
        history = []
    try:
        if lang == "hinglish":
            messages = [
                {
                    "role": "system",
                    "content": "You are a friendly assistant for people from Himachal Pradesh. Always reply in simple Hinglish. Short and conversational."
                }
            ]
            messages.extend(history)
            messages.append({"role": "user", "content": user_message})
            response = groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages
            )
            return response.choices[0].message.content
        else:
            hindi_answer = get_hindi_answer(user_message, history)
            pahari_answer = translate_to_pahari(hindi_answer, lang)
            return pahari_answer
    except Exception as e:
        print("AI error:", str(e))
        return "Maaf kariye, thodi dikkat aa rahi hai. Thodi der baad phir koshish karein."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_lang_map:
        user_lang_map[user_id] = DEFAULT_LANG
    await update.message.reply_text("Han G Maraj! Aaun Tusa Ra AI assistant aa")

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "Choose Language:\n/set_hinglish\n/set_pahari\n/set_kangri\n/set_mandyali"
    await update.message.reply_text(text)

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
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("set_hinglish", set_hinglish))
    app.add_handler(CommandHandler("set_pahari", set_pahari))
    app.add_handler(CommandHandler("set_kangri", set_kangri))
    app.add_handler(CommandHandler("set_mandyali", set_mandyali))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
