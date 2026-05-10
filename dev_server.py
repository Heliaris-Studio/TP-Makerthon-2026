#!/usr/bin/env python3
"""
本地開發用 Flask Server（不需要 RPi 硬體）
用途：專門用來測試 HTML 設計，所有 GPIO/感測器改用假資料
使用方法：python3 dev_server.py
"""
import os
import json
import queue
import threading
from flask import Flask, jsonify, Response, request, session, redirect, send_from_directory
from core.db import (init_db, get_account, get_all_students, get_room_by_student,
                     get_my_orders, get_pending_order, add_order, pickup_order,
                     get_room_points, add_room_points, redeem_room_points, get_all_room_points,
                     get_all_rooms_students, get_merchants, add_merchant,
                     get_rankings, get_room_monthly_stats, get_room_merchant_stats,
                     register_merchant, get_merchant_profile, update_merchant_menu,
                     get_all_merchant_profiles)
from core.ocr import parse_menu_image

app = Flask(__name__)
app.secret_key = 'dev-secret'

init_db()

# ── 即時積分推播（SSE）────────────────────────────────────
_room_subs: dict[str, list[queue.Queue]] = {}
_subs_lock = threading.Lock()

def _broadcast_points(room: str, points: int):
    with _subs_lock:
        dead = []
        for q in _room_subs.get(room, []):
            try:
                q.put_nowait(points)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _room_subs[room].remove(q)

# ── 硬體無關的常數 ────────────────────────────────────────
ROOM_SIDE    = {'B301': 'left', 'B302': 'left', 'B405': 'right', 'B406': 'right'}
BUTTON_ROOMS = {1: 'B301', 2: 'B302', 3: 'B405', 4: 'B406'}

FAKE_STATE = {
    "distance": 42.3,
    "recording": False,
    "door_left": "closed",
    "door_right": "closed",
    "led_l_green": False,
    "led_l_red": True,
    "led_r_green": False,
    "led_r_red": True,
    "last_event": "開發模式：無真實事件",
}

# ── 工具 ──────────────────────────────────────────────────
def _html(name):
    return open(os.path.join(os.path.dirname(__file__), 'html', name),
                encoding='utf-8').read()

def _require(*roles):
    acc = session.get('account')
    if not acc:
        return redirect('/login')
    if roles and acc['role'] not in roles:
        return redirect('/login')
    return None

# ── 頁面路由 ──────────────────────────────────────────────
@app.route('/')
def index():
    acc = session.get('account')
    if not acc:
        return redirect('/login')
    return redirect({'admin': '/admin-mobile', 'student': '/student',
                     'delivery': '/delivery', 'merchant': '/merchant'}.get(acc['role'], '/login'))

@app.route('/login')
def login_page():
    return _html('login.html')

@app.route('/student')
def student_page():
    r = _require('student')
    return r if r else _html('student.html')

@app.route('/delivery')
def delivery_page():
    r = _require('delivery')
    return r if r else _html('delivery.html')

@app.route('/admin-mobile')
def admin_mobile_page():
    r = _require('admin')
    return r if r else _html('admin_m.html')

@app.route('/merchant/register')
def merchant_register_page():
    return _html('merchant_register.html')

@app.route('/merchant')
def merchant_page():
    r = _require('merchant')
    return r if r else _html('merchant.html')

# ── API 路由（假資料）────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json(silent=True) or {}
    aid = data.get('id', '').strip()
    if not aid:
        return jsonify({"error": "請輸入帳號"}), 400
    acc = get_account(aid)
    if not acc:
        return jsonify({"error": "帳號不存在"}), 401
    session['account'] = acc
    return jsonify({"ok": True, "role": acc['role'], "name": acc['name']})

@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

@app.route('/api/me')
def api_me():
    acc = session.get('account')
    if not acc:
        return jsonify({"error": "not logged in"}), 401
    return jsonify({"name": acc['name'], "role": acc['role']})

@app.route('/api/status')
def api_status():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(FAKE_STATE)

@app.route('/api/door/<side>', methods=['POST'])
def api_door(side):
    if side not in ('left', 'right'):
        return jsonify({"error": "invalid"}), 400
    FAKE_STATE[f"door_{side}"] = "open"
    FAKE_STATE["last_event"] = f"[Dev] 管理員開 {side} 門"
    # 模擬 3 秒後自動關門
    def auto_close():
        import time; time.sleep(3)
        FAKE_STATE[f"door_{side}"] = "closed"
    threading.Thread(target=auto_close, daemon=True).start()
    return jsonify({"ok": True})

@app.route('/api/led/<side>/<color>/<action>', methods=['POST'])
def api_led(side, color, action):
    if side not in ('left', 'right') or color not in ('green', 'red') or action not in ('on', 'off'):
        return jsonify({"error": "invalid"}), 400
    green_on = (color == 'green' and action == 'on')
    FAKE_STATE[f"led_{side[0]}_green"] = green_on
    FAKE_STATE[f"led_{side[0]}_red"]   = not green_on
    return jsonify({"ok": True})

@app.route('/api/button/<int:btn_num>', methods=['POST'])
def api_button(btn_num):
    if btn_num not in BUTTON_ROOMS:
        return jsonify({"error": "invalid"}), 400
    room = BUTTON_ROOMS[btn_num]
    side = ROOM_SIDE[room]
    FAKE_STATE["last_event"] = f"[Dev] 按鈕{btn_num} ({room}) 觸發"
    FAKE_STATE[f"door_{side}"] = "open"
    def auto_close():
        import time; time.sleep(3)
        FAKE_STATE[f"door_{side}"] = "closed"
    threading.Thread(target=auto_close, daemon=True).start()
    return jsonify({"ok": True, "room": room, "side": side})

@app.route('/api/students')
def api_students():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_all_students())

@app.route('/api/my-orders')
def api_my_orders():
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    sid = acc['id']
    room = acc['room']
    return jsonify({
        "orders":  get_my_orders(sid),
        "points":  get_room_points(room),
        "pending": get_pending_order(sid),
        "name":    acc['name'],
        "room":    room,
    })

@app.route('/api/points-stream')
def api_points_stream():
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    room = acc['room']
    q = queue.Queue(maxsize=20)
    with _subs_lock:
        _room_subs.setdefault(room, []).append(q)

    def generate():
        try:
            yield f"data: {get_room_points(room)}\n\n"
            while True:
                try:
                    pts = q.get(timeout=25)
                    yield f"data: {pts}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _subs_lock:
                subs = _room_subs.get(room, [])
                if q in subs:
                    subs.remove(q)

    return Response(generate(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    """學生在合作商家內用後打卡加積分"""
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    import random
    room = acc['room']
    pts = random.randint(2, 6)
    total = add_room_points(room, pts)
    _broadcast_points(room, total)
    return jsonify({"ok": True, "added": pts, "total": total})

@app.route('/api/redeem', methods=['POST'])
def api_redeem():
    """兌換積分商店品項"""
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    cost = int(data.get('cost', 0))
    room = acc['room']
    ok, total = redeem_room_points(room, cost)
    if ok:
        _broadcast_points(room, total)
    return jsonify({"ok": ok, "total": total,
                    "error": "積分不足" if not ok else None})

@app.route('/api/open_by_student', methods=['POST'])
def api_open_by_student():
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    sid = acc['id']
    pending = get_pending_order(sid)
    if not pending:
        return jsonify({"error": "目前沒有待取餐點"}), 404
    room = acc['room']
    side = ROOM_SIDE.get(room)
    FAKE_STATE["last_event"] = f"[Dev] 學生 {acc['name']} ({room}) 開箱"
    FAKE_STATE[f"door_{side}"] = "open"
    pickup_order(pending['id'], sid)
    def auto_close():
        import time; time.sleep(3)
        FAKE_STATE[f"door_{side}"] = "closed"
    threading.Thread(target=auto_close, daemon=True).start()
    return jsonify({"ok": True, "room": room, "side": side})

@app.route('/api/delivery/rooms')
def api_delivery_rooms():
    r = _require('delivery')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_all_rooms_students())

@app.route('/api/delivery/open', methods=['POST'])
def api_delivery_open():
    r = _require('delivery')
    if r: return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    sid = data.get('student_id', '').strip()
    merchant = data.get('merchant', '外送').strip()
    room = get_room_by_student(sid)
    if not room:
        return jsonify({"error": "找不到學生"}), 404
    side = ROOM_SIDE.get(room)
    oid = add_order(sid, room, merchant)
    FAKE_STATE["last_event"] = f"[Dev] 外送員送達 {room} ({sid})"
    FAKE_STATE[f"door_{side}"] = "open"
    def auto_close():
        import time; time.sleep(3)
        FAKE_STATE[f"door_{side}"] = "closed"
    threading.Thread(target=auto_close, daemon=True).start()
    return jsonify({"ok": True, "order_id": oid, "room": room, "side": side})

@app.route('/api/videos/clear', methods=['POST'])
def clear_videos():
    return jsonify({"ok": True})  # 開發模式：no-op

@app.route('/api/rankings')
def api_rankings():
    r = _require('student', 'admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    month = request.args.get('month')
    return jsonify(get_rankings(month))

@app.route('/api/room-stats')
def api_room_stats():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_room_monthly_stats())

@app.route('/api/merchants')
def api_merchants():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_merchants())

@app.route('/api/merchants', methods=['POST'])
def api_add_merchant():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    if not name:
        return jsonify({"error": "店家名稱不能空白"}), 400
    add_merchant(name, category)
    return jsonify({"ok": True})

@app.route('/api/room-merchant-stats')
def api_room_merchant_stats():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_room_merchant_stats())

# ── 商家 API ──────────────────────────────────────────────

@app.route('/api/merchant/register', methods=['POST'])
def api_merchant_register():
    data = request.get_json(silent=True) or {}
    store_name  = data.get('store_name', '').strip()
    category    = data.get('category', '').strip()
    description = data.get('description', '').strip()
    if not store_name:
        return jsonify({"error": "請輸入店家名稱"}), 400
    account_id = register_merchant(store_name, category, description)
    return jsonify({"ok": True, "account_id": account_id, "store_name": store_name})

@app.route('/api/merchant/profile')
def api_merchant_profile():
    acc = session.get('account')
    if not acc or acc['role'] != 'merchant':
        return jsonify({"error": "unauthorized"}), 401
    profile = get_merchant_profile(acc['id'])
    if not profile:
        return jsonify({"error": "找不到商家資料"}), 404
    return jsonify(profile)

@app.route('/api/merchant/upload-menu', methods=['POST'])
def api_merchant_upload_menu():
    acc = session.get('account')
    if not acc or acc['role'] != 'merchant':
        return jsonify({"error": "unauthorized"}), 401
    if 'image' not in request.files:
        return jsonify({"error": "請上傳圖片"}), 400
    f = request.files['image']
    if not f.filename:
        return jsonify({"error": "未選擇圖片"}), 400
    # Validate file type
    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    mime = f.mimetype or 'image/jpeg'
    if mime not in allowed:
        return jsonify({"error": "僅支援 JPG / PNG / WebP 格式"}), 400
    image_bytes = f.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        return jsonify({"error": "圖片大小不能超過 10MB"}), 400
    try:
        items = parse_menu_image(image_bytes, mime)
    except Exception as e:
        return jsonify({"error": f"OCR 解析失敗：{str(e)}"}), 500
    return jsonify({"ok": True, "items": items})

@app.route('/api/merchant/menu', methods=['GET'])
def api_merchant_menu_get():
    acc = session.get('account')
    if not acc or acc['role'] != 'merchant':
        return jsonify({"error": "unauthorized"}), 401
    profile = get_merchant_profile(acc['id'])
    return jsonify(profile['menu'] if profile else [])

@app.route('/api/merchant/menu', methods=['POST'])
def api_merchant_menu_save():
    acc = session.get('account')
    if not acc or acc['role'] != 'merchant':
        return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    items = data.get('items', [])
    # Re-assign sequential IDs
    for i, item in enumerate(items):
        item['id'] = i + 1
    ok = update_merchant_menu(acc['id'], items)
    return jsonify({"ok": ok})

@app.route('/api/merchants/public')
def api_merchants_public():
    """學生端可查閱的商家列表（含菜單）"""
    profiles = get_all_merchant_profiles()
    return jsonify(profiles)

@app.route('/image/<path:filename>')
def serve_image(filename):
    img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'image')
    return send_from_directory(img_dir, filename)

# ── 相機 stream（開發模式回傳靜態圖）─────────────────────
@app.route('/stream')
def stream():
    def placeholder():
        # 回傳一張純色 JPEG 當作 placeholder
        try:
            import cv2, numpy as np
            img = np.zeros((240, 320, 3), dtype='uint8')
            img[:] = (40, 40, 40)
            cv2.putText(img, 'DEV MODE', (60, 120),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 0), 2)
            _, jpeg = cv2.imencode('.jpg', img)
            frame = jpeg.tobytes()
        except ImportError:
            # 如果連 cv2 都沒有，回傳最小 1x1 灰色 JPEG
            frame = (b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
                     b'\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t'
                     b'\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a'
                     b'\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\x1e'
                     b'\x1b\x1d3=853>73<8=\x0f\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01'
                     b'\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01'
                     b'\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07'
                     b'\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03'
                     b'\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!'
                     b'1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1'
                     b'\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJ'
                     b'STUVWXYZ\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xf5(\xa2\x80\x03'
                     b'\xff\xd9')
        import time
        while True:
            yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time.sleep(0.5)
    return Response(placeholder(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# ── 啟動 ──────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 50)
    print("  開發模式（無 RPi 硬體）")
    print("  可用帳號：admin / delivery / 學生ID（如 115A5206）")
    print("  http://localhost:5001")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=True)
