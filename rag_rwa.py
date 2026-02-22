import re
from datetime import datetime


class RWARAGSystem:
    def __init__(self):

        self.intents = {
            "add_flat": [
                "flat add karo", "naya flat", "flat jodo", "add flat",
                "ghar add karo", "unit add"
            ],
            "add_resident": [
                "resident add karo", "member add karo", "naya resident",
                "malik add karo", "owner add", "ghar wala add"
            ],
            "mark_paid": [
                "paid", "de diya", "jama kar diya", "pay kar diya",
                "maintenance de di", "due de diya", "payment ho gaya",
                "pay ho gaya", "bhar diya"
            ],
            "mark_pending": [
                "pending", "nahi diya", "baaki hai", "due hai",
                "nahi bharaa", "abhi tak nahi"
            ],
            "show_pending": [
                "pending list", "kisne nahi diya", "baaki list",
                "pending dikhao", "kaun baaki hai", "unpaid list",
                "kitne pending hain"
            ],
            "show_paid": [
                "paid list", "kisne diya", "payment list",
                "paid dikhao", "kaun paid hai"
            ],
            "send_reminder": [
                "reminder bhejo", "remind karo", "message bhejo pending ko",
                "alert bhejo", "pending walo ko batao"
            ],
            "send_alert": [
                "alert", "announcement", "notice bhejo", "sabko batao",
                "broadcast karo", "inform karo", "poori society ko"
            ],
            "maintenance_summary": [
                "summary", "kitna aaya", "total collection", "hisab batao",
                "kitne paid", "report dikhao", "status batao"
            ],
            "add_complaint": [
                "complaint", "shikayat", "problem hai", "issue hai",
                "kharabi hai", "theek karo", "repair"
            ],
            "show_complaints": [
                "complaints dikhao", "shikayat list", "pending complaints",
                "issues dikhao"
            ],
            "pdf_update": [
                "pdf", "file upload", "list upload", "record upload",
                "document", "excel"
            ],
            "my_status": [
                "mera status", "meri due", "mera maintenance",
                "maine diya", "mera baaki"
            ]
        }

    def detect_intent(self, text):
        text = text.lower().strip()
        for intent, keywords in self.intents.items():
            for keyword in keywords:
                if keyword in text:
                    return intent
        return "unknown"

    def extract_flat_number(self, text):
        text = text.upper()
        patterns = [
            r'FLAT\s*[-:]?\s*([A-Z]?\d+[A-Z]?)',
            r'([A-Z]\d+)',
            r'(\d{2,4}[A-Z]?)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None

    def extract_amount(self, text):
        patterns = [
            r'Rs\.?\s*(\d+)',
            r'(\d+)\s*rupay',
            r'(\d+)\s*rs',
            r'(\d{3,5})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return float(match.group(1))
        return None

    def extract_month(self, text):
        text = text.lower()
        months = {
            "january": "01", "jan": "01",
            "february": "02", "feb": "02",
            "march": "03", "mar": "03",
            "april": "04", "apr": "04",
            "may": "05",
            "june": "06", "jun": "06",
            "july": "07", "jul": "07",
            "august": "08", "aug": "08",
            "september": "09", "sep": "09",
            "october": "10", "oct": "10",
            "november": "11", "nov": "11",
            "december": "12", "dec": "12",
            "january": "01", "february": "02",
            "is mahine": None, "current": None,
            "pichle mahine": None
        }
        year = datetime.now().strftime("%Y")
        current_month = datetime.now().strftime("%Y-%m")

        for month_name, month_num in months.items():
            if month_name in text:
                if month_num:
                    return year + "-" + month_num
                else:
                    return current_month

        return current_month

    def extract_name(self, text):
        stop_words = [
            "flat", "resident", "member", "add", "karo", "ne", "ka",
            "ki", "ke", "paid", "pending", "maintenance", "due", "hai",
            "nahi", "diya", "de", "society", "alert", "complaint"
        ]
        words = text.lower().split()
        filtered = [w for w in words if w not in stop_words and len(w) > 2]
        if filtered:
            return filtered[0].capitalize()
        return None

    def parse_pdf_text(self, text):
        records = []
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            flat = self.extract_flat_number(line)
            if not flat:
                continue

            status = "pending"
            if any(word in line.lower() for word in ["paid", "yes", "haan", "de diya", "jama"]):
                status = "paid"
            elif any(word in line.lower() for word in ["pending", "no", "nahi", "baaki"]):
                status = "pending"

            amount = self.extract_amount(line)

            name_match = re.search(r'[A-Z][a-z]+ [A-Z][a-z]+', line)
            name = name_match.group(0) if name_match else None

            records.append({
                "flat": flat,
                "name": name,
                "status": status,
                "amount": amount or 0
            })

        return records

    def build_reminder_message(self, flat_number, resident_name, amount, month):
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        msg = (
            "Namaste " + (resident_name or "Resident") + " ji!\n\n"
            "Yeh ek automated reminder hai.\n\n"
            "Flat: " + flat_number + "\n"
            "Month: " + month_display + "\n"
            "Maintenance Due: Rs." + str(int(amount)) + "\n\n"
            "Kripya jald se jald maintenance jama karein.\n"
            "Dhanyawad!\n"
            "- RWA Committee"
        )
        return msg

    def build_alert_message(self, alert_type, title, message):
        emoji_map = {
            "maintenance": "💰",
            "water": "💧",
            "electricity": "⚡",
            "lift": "🛗",
            "security": "🔒",
            "event": "🎉",
            "emergency": "🚨",
            "general": "📢"
        }
        emoji = emoji_map.get(alert_type.lower(), "📢")
        msg = (
            emoji + " *Society Alert*\n\n"
            "*" + title + "*\n\n"
            + message + "\n\n"
            "- RWA Committee"
        )
        return msg

    def build_summary_text(self, summary, month):
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        total = summary["total"]
        paid = summary["paid"]
        pending_count = (total["total"] or 0) - (paid["paid_count"] or 0)
        pending_amount = (total["total_amount"] or 0) - (paid["paid_amount"] or 0)

        text = (
            "📊 *Maintenance Summary*\n"
            "*" + month_display + "*\n\n"
            "Total Flats: " + str(total["total"] or 0) + "\n"
            "Total Amount: Rs." + str(int(total["total_amount"] or 0)) + "\n\n"
            "Paid:\n"
            "  Flats: " + str(paid["paid_count"] or 0) + "\n"
            "  Amount: Rs." + str(int(paid["paid_amount"] or 0)) + "\n\n"
            "Pending:\n"
            "  Flats: " + str(pending_count) + "\n"
            "  Amount: Rs." + str(int(pending_amount)) + "\n\n"
        )

        if total["total"] and total["total"] > 0:
            percent = int(((paid["paid_count"] or 0) / total["total"]) * 100)
            text += "Collection: " + str(percent) + "%"

        return text
