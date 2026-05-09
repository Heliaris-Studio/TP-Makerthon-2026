import sqlite3
import random
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'heliaris.db')

ROOMS = ['B301', 'B302', 'B405', 'B406']

_NAMES = [
    '林宜蓁', '陳柏宇', '張雅婷', '黃冠霖', '李思穎',
    '王建志', '吳佳玲', '劉宗翰', '蔡雨晴', '許志豪',
    '鄭怡君', '謝明哲', '洪思妤', '簡宏達', '曾雅雯',
    '蘇彥廷', '楊欣妤', '賴俊宏', '江美如', '羅子緯',
]

def _rand_student_id(existing: set) -> str:
    depts = ['A', 'B', 'C', 'D']
    while True:
        sid = f"115{random.choice(depts)}{random.randint(1000, 9999):04d}"
        if sid not in existing:
            existing.add(sid)
            return sid

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            room       TEXT NOT NULL
        )
    ''')
    c.execute('SELECT COUNT(*) FROM students')
    if c.fetchone()[0] == 0:
        used_ids = set()
        names = _NAMES.copy()
        random.shuffle(names)
        rows = []
        for i, room in enumerate(ROOMS):
            count = random.randint(1, 3)
            for _ in range(count):
                sid = _rand_student_id(used_ids)
                name = names.pop() if names else f"學生{len(rows)+1}"
                rows.append((sid, name, room))
        c.executemany('INSERT INTO students VALUES (?,?,?)', rows)
        conn.commit()
        print(f"[DB] 初始化完成，共 {len(rows)} 位學生")
    conn.close()

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
