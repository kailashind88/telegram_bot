import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path="rwa_bot.db"):
        self.db_path = db_path

    def get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        with self.get_conn() as conn:
            conn.executescript("""

                -- Societies
                CREATE TABLE IF NOT EXISTS societies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_group_id TEXT UNIQUE NOT NULL,
                    society_name TEXT DEFAULT 'Meri Society',
                    address TEXT,
                    admin_chat_id TEXT,
                    created_at TEXT NOT NULL
                );

                -- Flats
                CREATE TABLE IF NOT EXISTS flats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    society_id INTEGER NOT NULL,
                    flat_number TEXT NOT NULL,
                    floor TEXT,
                    block TEXT,
                    FOREIGN KEY (society_id) REFERENCES societies(id)
                );

                -- Residents (naam aur mobile required)
                CREATE TABLE IF NOT EXISTS residents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flat_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    mobile TEXT,
                    telegram_chat_id TEXT,
                    is_owner INTEGER DEFAULT 1,
                    is_verified INTEGER DEFAULT 0,
                    added_by TEXT DEFAULT 'admin',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (flat_id) REFERENCES flats(id)
                );

                -- Maintenance dues
                CREATE TABLE IF NOT EXISTS maintenance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flat_id INTEGER NOT NULL,
                    month TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    paid_date TEXT,
                    payment_mode TEXT,
                    receipt_number TEXT,
                    notes TEXT,
                    FOREIGN KEY (flat_id) REFERENCES flats(id)
                );

                -- Alerts
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    society_id INTEGER NOT NULL,
                    alert_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_by TEXT,
                    created_at TEXT NOT NULL,
                    is_sent INTEGER DEFAULT 0,
                    FOREIGN KEY (society_id) REFERENCES societies(id)
                );

                -- Complaints
                CREATE TABLE IF NOT EXISTS complaints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    flat_id INTEGER NOT NULL,
                    complaint_text TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    resolved_at TEXT,
                    FOREIGN KEY (flat_id) REFERENCES flats(id)
                );

            """)
        print("RWA Database ready!")

    # ── Society ─────────────────────────────────────────────────

    def get_or_create_society(self, group_id, society_name="Meri Society"):
        group_id = str(group_id)
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM societies WHERE telegram_group_id=?", (group_id,)
            ).fetchone()
            if not row:
                conn.execute(
                    "INSERT INTO societies (telegram_group_id, society_name, created_at) VALUES (?, ?, ?)",
                    (group_id, society_name, datetime.now().strftime("%Y-%m-%d"))
                )
                row = conn.execute(
                    "SELECT * FROM societies WHERE telegram_group_id=?", (group_id,)
                ).fetchone()
        return dict(row)

    def set_admin(self, society_id, admin_chat_id):
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE societies SET admin_chat_id=? WHERE id=?",
                (str(admin_chat_id), society_id)
            )

   def is_admin(self, society_id, chat_id):
    if ADMIN_CHAT_ID and str(chat_id) == ADMIN_CHAT_ID:
        return True

    # ── Flats ───────────────────────────────────────────────────

    def add_flat(self, society_id, flat_number, floor=None, block=None):
        flat_number = flat_number.upper().strip()
        with self.get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM flats WHERE society_id=? AND flat_number=?",
                (society_id, flat_number)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO flats (society_id, flat_number, floor, block) VALUES (?, ?, ?, ?)",
                    (society_id, flat_number, floor, block)
                )
        return self.get_flat(society_id, flat_number)

    def get_flat(self, society_id, flat_number):
        flat_number = flat_number.upper().strip()
        with self.get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM flats WHERE society_id=? AND flat_number=?",
                (society_id, flat_number)
            ).fetchone()
        return dict(row) if row else None

    def get_all_flats(self, society_id):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM flats WHERE society_id=? ORDER BY flat_number",
                (society_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Residents ───────────────────────────────────────────────

    def add_resident(self, flat_id, name, mobile=None, telegram_chat_id=None, added_by="admin"):
        """Resident add karo — naam aur mobile ke saath"""
        with self.get_conn() as conn:
            # Check if already exists
            existing = conn.execute(
                "SELECT id FROM residents WHERE flat_id=? AND name=?",
                (flat_id, name)
            ).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO residents
                       (flat_id, name, mobile, telegram_chat_id, added_by, created_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (flat_id, name, mobile, telegram_chat_id,
                     added_by, datetime.now().strftime("%Y-%m-%d"))
                )
                return True
        return False

    def update_resident_mobile(self, flat_id, name, mobile):
        """Mobile number update karo"""
        with self.get_conn() as conn:
            conn.execute(
                "UPDATE residents SET mobile=? WHERE flat_id=? AND name LIKE ?",
                (mobile, flat_id, f"%{name}%")
            )

    def update_resident_telegram(self, telegram_chat_id, flat_number, society_id):
        """Jab resident /start kare toh Telegram ID link karo"""
        flat = self.get_flat(society_id, flat_number)
        if not flat:
            return False
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE residents SET telegram_chat_id=?, is_verified=1
                   WHERE flat_id=? AND is_verified=0""",
                (str(telegram_chat_id), flat["id"])
            )
        return True

    def get_residents_by_flat(self, flat_id):
        with self.get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM residents WHERE flat_id=?", (flat_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_resident_by_telegram(self, telegram_chat_id):
        with self.get_conn() as conn:
            row = conn.execute(
                """SELECT r.*, f.flat_number, f.society_id
                   FROM residents r JOIN flats f ON r.flat_id=f.id
                   WHERE r.telegram_chat_id=?""",
                (str(telegram_chat_id),)
            ).fetchone()
        return dict(row) if row else None

    def get_all_residents(self, society_id):
        """Poori society ke residents — naam aur mobile ke saath"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT r.id, r.name, r.mobile, r.telegram_chat_id,
                          r.is_verified, f.flat_number, f.block
                   FROM residents r
                   JOIN flats f ON r.flat_id=f.id
                   WHERE f.society_id=?
                   ORDER BY f.flat_number""",
                (society_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_residents_with_telegram(self, society_id):
        """Sirf woh residents jinke paas Telegram hai"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT r.*, f.flat_number FROM residents r
                   JOIN flats f ON r.flat_id=f.id
                   WHERE f.society_id=? AND r.telegram_chat_id IS NOT NULL""",
                (society_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def search_resident(self, society_id, search_term):
        """Naam ya mobile se resident dhundo"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT r.*, f.flat_number FROM residents r
                   JOIN flats f ON r.flat_id=f.id
                   WHERE f.society_id=?
                   AND (r.name LIKE ? OR r.mobile LIKE ? OR f.flat_number LIKE ?)""",
                (society_id, f"%{search_term}%", f"%{search_term}%", f"%{search_term}%")
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Maintenance ─────────────────────────────────────────────

    def add_maintenance_record(self, flat_id, month, amount, status="pending"):
        with self.get_conn() as conn:
            existing = conn.execute(
                "SELECT id FROM maintenance WHERE flat_id=? AND month=?",
                (flat_id, month)
            ).fetchone()
            if not existing:
                conn.execute(
                    "INSERT INTO maintenance (flat_id, month, amount, status) VALUES (?, ?, ?, ?)",
                    (flat_id, month, amount, status)
                )
            else:
                conn.execute(
                    "UPDATE maintenance SET status=?, amount=? WHERE flat_id=? AND month=?",
                    (status, amount, flat_id, month)
                )

    def mark_paid(self, flat_id, month, payment_mode=None):
        with self.get_conn() as conn:
            conn.execute(
                """UPDATE maintenance SET status='paid', paid_date=?, payment_mode=?
                   WHERE flat_id=? AND month=?""",
                (datetime.now().strftime("%Y-%m-%d"), payment_mode, flat_id, month)
            )

    def get_maintenance_status(self, society_id, month):
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT f.flat_number, r.name, r.mobile, r.telegram_chat_id,
                          m.amount, m.status, m.paid_date
                   FROM maintenance m
                   JOIN flats f ON m.flat_id=f.id
                   LEFT JOIN residents r ON r.flat_id=f.id
                   WHERE f.society_id=? AND m.month=?
                   ORDER BY f.flat_number""",
                (society_id, month)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_pending_list(self, society_id, month):
        """Pending walo ki list — naam aur mobile ke saath"""
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT f.flat_number, r.name, r.mobile,
                          r.telegram_chat_id, m.amount
                   FROM maintenance m
                   JOIN flats f ON m.flat_id=f.id
                   LEFT JOIN residents r ON r.flat_id=f.id
                   WHERE f.society_id=? AND m.month=? AND m.status='pending'
                   ORDER BY f.flat_number""",
                (society_id, month)
            ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self, society_id, month):
        with self.get_conn() as conn:
            total = conn.execute(
                """SELECT COUNT(*) as total, SUM(amount) as total_amount
                   FROM maintenance m JOIN flats f ON m.flat_id=f.id
                   WHERE f.society_id=? AND m.month=?""",
                (society_id, month)
            ).fetchone()
            paid = conn.execute(
                """SELECT COUNT(*) as paid_count, SUM(amount) as paid_amount
                   FROM maintenance m JOIN flats f ON m.flat_id=f.id
                   WHERE f.society_id=? AND m.month=? AND m.status='paid'""",
                (society_id, month)
            ).fetchone()
        return {"total": dict(total), "paid": dict(paid)}

    # ── Alerts ──────────────────────────────────────────────────

    def add_alert(self, society_id, alert_type, title, message, created_by=None):
        with self.get_conn() as conn:
            conn.execute(
                """INSERT INTO alerts
                   (society_id, alert_type, title, message, created_by, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (society_id, alert_type, title, message,
                 created_by, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )

    def get_recent_alerts(self, society_id, limit=5):
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM alerts WHERE society_id=?
                   ORDER BY created_at DESC LIMIT ?""",
                (society_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Complaints ──────────────────────────────────────────────

    def add_complaint(self, flat_id, complaint_text):
        with self.get_conn() as conn:
            conn.execute(
                "INSERT INTO complaints (flat_id, complaint_text, created_at) VALUES (?, ?, ?)",
                (flat_id, complaint_text, datetime.now().strftime("%Y-%m-%d %H:%M"))
            )

    def get_pending_complaints(self, society_id):
        with self.get_conn() as conn:
            rows = conn.execute(
                """SELECT c.*, f.flat_number FROM complaints c
                   JOIN flats f ON c.flat_id=f.id
                   WHERE f.society_id=? AND c.status='pending'
                   ORDER BY c.created_at DESC""",
                (society_id,)
            ).fetchall()
        return [dict(r) for r in rows]
