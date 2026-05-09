import sqlite3
import random
import datetime
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'heliaris.db')

ROOMS = ['B301', 'B302', 'B405', 'B406']

_FIXED_STUDENTS = [
    ('115A5206', '林宜蓁', 'B301'),
    ('115A1033', '陳柏宇', 'B301'),
    ('115B2201', '張雅婷', 'B302'),
    ('115B3847', '黃冠霖', 'B302'),
    ('115C4412', '李思穎', 'B405'),
    ('115C5509', '王建志', 'B405'),
    ('115D6618', '吳佳玲', 'B406'),
    ('115D7723', '劉宗翰', 'B406'),
]

_MERCHANTS = ['麥當勞', '肯德基', '摩斯漢堡', '爭鮮壽司', '鬍鬚張', '85度C', '星巴克', '丹堤咖啡', '50嵐', '清心福全']

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS accounts (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        room TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        room TEXT NOT NULL
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        room TEXT NOT NULL,
        merchant TEXT NOT NULL,
        month TEXT NOT NULL,
        delivered_at TEXT,
        picked_up_at TEXT,
        status TEXT DEFAULT 'pending'
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS merchants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        category TEXT DEFAULT ''
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS points (
        student_id TEXT PRIMARY KEY,
        total INTEGER DEFAULT 0
    )''')

    c.execute('SELECT COUNT(*) FROM accounts')
    if c.fetchone()[0] == 0:
        c.executemany('INSERT INTO students VALUES (?,?,?)', _FIXED_STUDENTS)
        c.executemany('INSERT INTO accounts VALUES (?,?,?,?)',
                      [(s[0], s[1], 'student', s[2]) for s in _FIXED_STUDENTS])
        c.execute('INSERT INTO accounts VALUES (?,?,?,?)', ('admin', '管理員', 'admin', None))
        c.execute('INSERT INTO accounts VALUES (?,?,?,?)', ('delivery', '外送員', 'delivery', None))

        today = datetime.date.today()
        order_rows = []
        point_map = {s[0]: 100 for s in _FIXED_STUDENTS}
        for s in _FIXED_STUDENTS:
            for mo in range(3):
                m = (today.replace(day=1) - datetime.timedelta(days=mo*30)).strftime('%Y-%m')
                count = random.randint(0, 8)
                for _ in range(count):
                    day = random.randint(1, 28)
                    ts = f"{m}-{day:02d} {random.randint(10,22):02d}:{random.randint(0,59):02d}:00"
                    order_rows.append((s[0], s[2], random.choice(_MERCHANTS), m, ts, ts, 'picked_up'))
                point_map[s[0]] = max(0, point_map[s[0]] - count * 8)

        c.executemany('INSERT INTO orders (student_id,room,merchant,month,delivered_at,picked_up_at,status) VALUES (?,?,?,?,?,?,?)',
                      order_rows)
        c.executemany('INSERT INTO points VALUES (?,?)', list(point_map.items()))

        c.executemany("INSERT OR IGNORE INTO merchants (name, category) VALUES (?,?)", [
            ('麥當勞','速食'), ('肯德基','速食'), ('摩斯漢堡','速食'),
            ('爭鮮壽司','日式'), ('鬍鬚張','台式'), ('85度C','飲料/甜點'),
            ('星巴克','咖啡'), ('丹堤咖啡','咖啡'), ('50嵐','飲料'), ('清心福全','飲料'),
        ])

        conn.commit()
        print(f"[DB] 初始化完成，共 {len(_FIXED_STUDENTS)} 位學生，{len(order_rows)} 筆歷史訂單")
    conn.close()

def get_account(aid: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, role, room FROM accounts WHERE id=?', (aid,))
    row = c.fetchone()
    conn.close()
    return {"id": row[0], "name": row[1], "role": row[2], "room": row[3]} if row else None

def get_room_by_student(student_id: str) -> str | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT room FROM students WHERE student_id=?', (student_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def get_all_students() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT student_id, name, room FROM students ORDER BY room, student_id')
    rows = [{"student_id": r[0], "name": r[1], "room": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def get_my_orders(student_id: str) -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id,merchant,month,status,delivered_at FROM orders WHERE student_id=? ORDER BY id DESC LIMIT 20',
              (student_id,))
    rows = [{"id": r[0], "merchant": r[1], "month": r[2], "status": r[3], "delivered_at": r[4]} for r in c.fetchall()]
    conn.close()
    return rows

def get_pending_order(student_id: str) -> dict | None:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id,merchant FROM orders WHERE student_id=? AND status='delivered' ORDER BY id DESC LIMIT 1",
              (student_id,))
    row = c.fetchone()
    conn.close()
    return {"id": row[0], "merchant": row[1]} if row else None

def add_order(student_id: str, room: str, merchant: str) -> int:
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    month = now[:7]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO orders (student_id,room,merchant,month,delivered_at,status) VALUES (?,?,?,?,?,'delivered')",
              (student_id, room, merchant, month, now))
    oid = c.lastrowid
    conn.commit()
    conn.close()
    return oid

def pickup_order(order_id: int, student_id: str):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE orders SET status='picked_up', picked_up_at=? WHERE id=? AND student_id=?",
              (now, order_id, student_id))
    if c.rowcount:
        pts = random.randint(2, 5)
        c.execute('INSERT INTO points (student_id,total) VALUES (?,?) ON CONFLICT(student_id) DO UPDATE SET total=total+?',
                  (student_id, pts, pts))
    conn.commit()
    conn.close()

def get_points(student_id: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT total FROM points WHERE student_id=?', (student_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def get_room_monthly_stats() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT room, month, COUNT(*) as cnt FROM orders GROUP BY room, month ORDER BY month DESC, room''')
    rows = [{"room": r[0], "month": r[1], "count": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def get_rankings(month: str = None) -> list:
    if not month:
        month = datetime.date.today().strftime('%Y-%m')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT room, COUNT(*) as cnt FROM orders WHERE month=? GROUP BY room ORDER BY cnt ASC''', (month,))
    rows = [{"room": r[0], "count": r[1]} for r in c.fetchall()]
    missing = [r for r in ROOMS if r not in [x["room"] for x in rows]]
    rows = [{"room": r, "count": 0} for r in missing] + rows
    rows.sort(key=lambda x: x["count"])
    conn.close()
    return rows

def get_merchants() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, category FROM merchants ORDER BY category, name')
    rows = [{"id": r[0], "name": r[1], "category": r[2]} for r in c.fetchall()]
    conn.close()
    return rows

def add_merchant(name: str, category: str = ''):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO merchants (name, category) VALUES (?,?)', (name, category))
    conn.commit()
    conn.close()

def get_all_rooms_students() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT student_id, name, room FROM students ORDER BY room')
    rows = c.fetchall()
    conn.close()
    result = {}
    for sid, name, room in rows:
        result.setdefault(room, []).append({"student_id": sid, "name": name})
    return [{"room": k, "students": v} for k, v in result.items()]
