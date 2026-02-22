import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
from groq import Groq
import PyPDF2
import io

from database import Database
from rag import RWARAGSystem

logging.basicConfig(level=logging.INFO)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN not set!")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY not set!")

db = Database()
rag = RWARAGSystem()
groq_client = Groq(api_key=GROQ_API_KEY)

def get_groq_response(prompt):
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": "You are a helpful RWA society manager assistant. Reply in Hinglish. Be concise and helpful."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        logging.error("Groq error: " + str(e))
        return "Kuch dikkat aayi. Dobara koshish karein."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    resident = db.get_resident_by_telegram(chat_id)
    if resident:
        await update.message.reply_text(
            "Namaste " + resident["name"] + " ji!\n"
            "Aap Flat " + resident["flat_number"] + " se registered hain.\n\n"
            "/status - Apni due dekho\n"
            "/complaint - Complaint darj karo\n"
            "/alerts - Recent alerts dekho"
        )
        return

    society = db.get_or_create_society(chat_id)
    await update.message.reply_text(
        "Namaste! RWA Bot mein aapka swagat hai!\n\n"
        "Kya aap:\n"
        "1. Admin hain? /admin likho\n"
        "2. Resident hain? Apna flat number likho (jaise: 302)"
    )
    context.user_data["waiting_for"] = "flat_number"
    context.user_data["society_id"] = society["id"]

async def admin_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)
    db.set_admin(society["id"], chat_id)
    await update.message.reply_text(
        "Admin setup ho gaya!\n\n"
        "*Admin Commands:*\n"
        "/add - Resident add karo\n"
        "/pending - Pending list dekho\n"
        "/paid - Paid mark karo\n"
        "/reminder - Reminders bhejo\n"
        "/alert - Society alert bhejo\n"
        "/summary - Monthly summary\n"
        "/residents - Saare residents\n"
        "/upload - PDF se update karo",
        parse_mode="Markdown"
    )

async def add_resident_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin yeh kar sakta hai.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Format:\n"
            "`/add 302 Sharma 9876543210`\n\n"
            "Flat Number - Naam - Mobile (optional)",
            parse_mode="Markdown"
        )
        return

    flat_number = context.args[0]
    name = context.args[1]
    mobile = context.args[2] if len(context.args) > 2 else None

    flat = db.add_flat(society["id"], flat_number)
    success = db.add_resident(flat["id"], name, mobile=mobile, added_by="admin")

    if success:
        msg = "Resident add ho gaya!\n\nFlat: " + flat_number + "\nNaam: " + name
        if mobile:
            msg += "\nMobile: " + mobile
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Yeh resident pehle se exist karta hai.")

async def show_residents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin dekh sakta hai.")
        return

    residents = db.get_all_residents(society["id"])
    if not residents:
        await update.message.reply_text("Abhi koi resident registered nahi hai.")
        return

    text = "*Saare Residents:*\n\n"
    for r in residents:
        text += "Flat " + r["flat_number"] + " - " + r["name"]
        if r["mobile"]:
            text += " - " + r["mobile"]
        if r["is_verified"]:
            text += " - Verified"
        text += "\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def set_maintenance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin yeh kar sakta hai.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Format:\n`/setdue 3500`\n\nYeh amount is mahine ke liye saare flats pe set ho jaayegi.",
            parse_mode="Markdown"
        )
        return

    try:
        amount = float(context.args[0])
    except:
        await update.message.reply_text("Amount sahi daalo. Jaise: `/setdue 3500`", parse_mode="Markdown")
        return

    month = datetime.now().strftime("%Y-%m")
    flats = db.get_all_flats(society["id"])

    if not flats:
        await update.message.reply_text("Pehle flats add karo. /add use karo.")
        return

    for flat in flats:
        db.add_maintenance_record(flat["id"], month, amount, status="pending")

    await update.message.reply_text(
        "Is mahine ki due set ho gayi!\n\n"
        "Amount: Rs." + str(int(amount)) + "\n"
        "Flats: " + str(len(flats)) + "\n"
        "Month: " + datetime.now().strftime("%B %Y")
    )

async def mark_paid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin yeh kar sakta hai.")
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n`/paid 302`\n\nFlat number daalo.",
            parse_mode="Markdown"
        )
        return

    flat_number = context.args[0]
    month = datetime.now().strftime("%Y-%m")
    flat = db.get_flat(society["id"], flat_number)

    if not flat:
        await update.message.reply_text("Flat " + flat_number + " nahi mila.")
        return

    db.mark_paid(flat["id"], month)
    residents = db.get_residents_by_flat(flat["id"])
    name = residents[0]["name"] if residents else "Resident"

    await update.message.reply_text(
        "Paid mark ho gaya!\n\n"
        "Flat: " + flat_number + "\n"
        "Naam: " + name + "\n"
        "Month: " + datetime.now().strftime("%B %Y")
    )

    if residents and residents[0].get("telegram_chat_id"):
        try:
            await context.bot.send_message(
                chat_id=residents[0]["telegram_chat_id"],
                text="Aapki maintenance payment confirm ho gayi!\n"
                     "Month: " + datetime.now().strftime("%B %Y") + "\n"
                     "Dhanyawad!\n- RWA Committee"
            )
        except:
            pass

async def show_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin dekh sakta hai.")
        return

    month = datetime.now().strftime("%Y-%m")
    pending = db.get_pending_list(society["id"], month)

    if not pending:
        await update.message.reply_text("Is mahine sab ne pay kar diya!")
        return

    text = "*Pending List - " + datetime.now().strftime("%B %Y") + "*\n\n"
    for i, p in enumerate(pending, 1):
        text += str(i) + ". Flat " + p["flat_number"]
        if p["name"]:
            text += " - " + p["name"]
        if p["mobile"]:
            text += " - " + p["mobile"]
        text += " - Rs." + str(int(p["amount"])) + "\n"

    text += "\nTotal pending: " + str(len(pending))
    await update.message.reply_text(text, parse_mode="Markdown")

async def send_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin yeh kar sakta hai.")
        return

    month = datetime.now().strftime("%Y-%m")
    pending = db.get_pending_list(society["id"], month)

    if not pending:
        await update.message.reply_text("Koi pending nahi hai!")
        return

    sent = 0
    no_telegram = 0

    for p in pending:
        if p.get("telegram_chat_id"):
            msg = rag.build_reminder_message(
                p["flat_number"], p["name"], p["amount"], month
            )
            try:
                await context.bot.send_message(chat_id=p["telegram_chat_id"], text=msg)
                sent += 1
            except:
                pass
        else:
            no_telegram += 1

    await update.message.reply_text(
        "Reminders bhej diye!\n\n"
        "Telegram pe bheja: " + str(sent) + "\n"
        "Telegram nahi hai: " + str(no_telegram) + "\n\n"
        "Jin logon ka Telegram nahi hai unhe manually call karein:\n" +
        "\n".join([
            "Flat " + p["flat_number"] + " - " + (p["name"] or "") + " - " + (p["mobile"] or "No mobile")
            for p in pending if not p.get("telegram_chat_id")
        ])
    )

async def send_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin alert bhej sakta hai.")
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n`/alert Paani kal band rahega 10 baje se 2 baje tak`",
            parse_mode="Markdown"
        )
        context.user_data["waiting_for"] = "alert_message"
        return

    message = " ".join(context.args)
    db.add_alert(society["id"], "general", "Society Notice", message, str(chat_id))

    residents = db.get_residents_with_telegram(society["id"])
    sent = 0
    alert_msg = "📢 *Society Alert*\n\n" + message + "\n\n- RWA Committee"

    for r in residents:
        try:
            await context.bot.send_message(
                chat_id=r["telegram_chat_id"],
                text=alert_msg,
                parse_mode="Markdown"
            )
            sent += 1
        except:
            pass

    await update.message.reply_text(
        "Alert bhej diya!\n" + str(sent) + " residents ko message gaya."
    )

async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin dekh sakta hai.")
        return

    month = datetime.now().strftime("%Y-%m")
    summary = db.get_summary(society["id"], month)
    text = rag.build_summary_text(summary, month)
    await update.message.reply_text(text, parse_mode="Markdown")

async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    resident = db.get_resident_by_telegram(chat_id)

    if not resident:
        await update.message.reply_text("Aap registered nahi hain. /start se register karein.")
        return

    month = datetime.now().strftime("%Y-%m")
    flat = db.get_flat(resident["society_id"], resident["flat_number"])
    records = db.get_maintenance_status(resident["society_id"], month)

    status_text = "Koi record nahi mila."
    for r in records:
        if r["flat_number"] == resident["flat_number"]:
            status_text = (
                "*Aapka Maintenance Status*\n\n"
                "Flat: " + r["flat_number"] + "\n"
                "Month: " + datetime.now().strftime("%B %Y") + "\n"
                "Amount: Rs." + str(int(r["amount"])) + "\n"
                "Status: " + ("Paid" if r["status"] == "paid" else "Pending") + "\n"
            )
            if r["paid_date"]:
                status_text += "Paid Date: " + r["paid_date"]
            break

    await update.message.reply_text(status_text, parse_mode="Markdown")

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin PDF upload kar sakta hai.")
        return

    await update.message.reply_text("PDF mil gayi! Process ho rahi hai...")

    file = await update.message.document.get_file()
    file_bytes = await file.download_as_bytearray()

    try:
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(bytes(file_bytes)))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() + "\n"

        prompt = (
            "Yeh ek society maintenance record hai PDF se extract kiya gaya:\n\n"
            + text + "\n\n"
            "Is text se har flat ka maintenance status nikalo.\n"
            "Format mein do:\n"
            "FLAT: [number] | NAME: [naam] | STATUS: [paid/pending] | AMOUNT: [amount]\n\n"
            "Sirf yeh format mein do, kuch aur mat likho."
        )

        groq_response = get_groq_response(prompt)
        records = []
        month = datetime.now().strftime("%Y-%m")

        for line in groq_response.split("\n"):
            if "FLAT:" in line:
                try:
                    parts = {}
                    for part in line.split("|"):
                        key, val = part.split(":")
                        parts[key.strip()] = val.strip()

                    flat_num = parts.get("FLAT", "").strip()
                    name = parts.get("NAME", "").strip()
                    status = parts.get("STATUS", "pending").strip().lower()
                    amount = float(parts.get("AMOUNT", "0").replace("Rs.", "").replace(",", "").strip() or 0)

                    if flat_num:
                        flat = db.add_flat(society["id"], flat_num)
                        if name and name != "Unknown":
                            db.add_resident(flat["id"], name, added_by="pdf")
                        db.add_maintenance_record(flat["id"], month, amount, status)
                        records.append(flat_num + " - " + status)
                except:
                    continue

        if records:
            await update.message.reply_text(
                "PDF se update ho gaya!\n\n"
                "Updated records: " + str(len(records)) + "\n\n"
                "Summary dekhne ke liye /summary likho."
            )
        else:
            await update.message.reply_text(
                "PDF process ho gayi lekin records extract nahi ho sake.\n"
                "PDF ka format check karein."
            )
    except Exception as e:
        logging.error("PDF error: " + str(e))
        await update.message.reply_text("PDF process karne mein error aaya. Format check karein.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    waiting = context.user_data.get("waiting_for")

    if waiting == "flat_number":
        flat_number = text.upper().strip()
        society_id = context.user_data.get("society_id")
        society = db.get_or_create_society(chat_id)

        success = db.update_resident_telegram(chat_id, flat_number, society["id"])
        if success:
            resident = db.get_resident_by_telegram(chat_id)
            name = resident["name"] if resident else "Resident"
            await update.message.reply_text(
                "Verified! Namaste " + name + " ji!\n\n"
                "Ab aapko society alerts milenge.\n\n"
                "/status - Apni due dekho\n"
                "/complaint - Complaint darj karo"
            )
        else:
            await update.message.reply_text(
                "Flat " + flat_number + " nahi mila.\n"
                "Admin se contact karein apna flat register karne ke liye."
            )
        context.user_data.pop("waiting_for", None)
        return

    intent = rag.detect_intent(text)

    if intent == "show_pending":
        await show_pending(update, context)
    elif intent == "maintenance_summary":
        await show_summary(update, context)
    elif intent == "send_reminder":
        await send_reminders(update, context)
    elif intent == "my_status":
        await my_status(update, context)
    else:
        response = get_groq_response(
            "RWA society bot hai. User ne kaha: '" + text + "'\n"
            "Helpful reply do Hinglish mein. Available commands bhi batao:\n"
            "/status, /complaint, /alert, /pending, /summary"
        )
        await update.message.reply_text(response)

async def add_complaint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    resident = db.get_resident_by_telegram(chat_id)

    if not resident:
        await update.message.reply_text("Pehle /start karke register karein.")
        return

    if not context.args:
        await update.message.reply_text(
            "Format:\n`/complaint Lift kharab hai`",
            parse_mode="Markdown"
        )
        return

    complaint_text = " ".join(context.args)
    flat = db.get_flat(resident["society_id"], resident["flat_number"])
    db.add_complaint(flat["id"], complaint_text)

    await update.message.reply_text(
        "Complaint darj ho gayi!\n\n"
        "Flat: " + resident["flat_number"] + "\n"
        "Complaint: " + complaint_text + "\n\n"
        "RWA committee jald se jald resolve karegi."
    )

async def show_complaints(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    society = db.get_or_create_society(chat_id)

    if not db.is_admin(society["id"], chat_id):
        await update.message.reply_text("Sirf admin dekh sakta hai.")
        return

    complaints = db.get_pending_complaints(society["id"])
    if not complaints:
        await update.message.reply_text("Koi pending complaint nahi hai!")
        return

    text = "*Pending Complaints:*\n\n"
    for i, c in enumerate(complaints, 1):
        text += str(i) + ". Flat " + c["flat_number"] + "\n"
        text += "   " + c["complaint_text"] + "\n"
        text += "   " + c["created_at"] + "\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    db.init_db()
    print("RWA Bot starting...")

    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_setup))
    app.add_handler(CommandHandler("add", add_resident_command))
    app.add_handler(CommandHandler("residents", show_residents))
    app.add_handler(CommandHandler("setdue", set_maintenance))
    app.add_handler(CommandHandler("paid", mark_paid_command))
    app.add_handler(CommandHandler("pending", show_pending))
    app.add_handler(CommandHandler("reminder", send_reminders))
    app.add_handler(CommandHandler("alert", send_alert))
    app.add_handler(CommandHandler("summary", show_summary))
    app.add_handler(CommandHandler("status", my_status))
    app.add_handler(CommandHandler("complaint", add_complaint))
    app.add_handler(CommandHandler("complaints", show_complaints))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_pdf))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
