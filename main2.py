#!/usr/bin/env python3
import os
import glob
import time
import threading
import RPi.GPIO as GPIO
from flask import Flask, jsonify, Response, request, session, redirect
import core.config as cfg
from core.doors import init as doors_init, open_door, set_led
from core.sensor import start as sensor_start, stop as sensor_stop
from core.db import (init_db, get_account, get_all_students, get_room_by_student,
                     get_my_orders, get_pending_order, add_order, pickup_order,
                     get_points, get_room_monthly_stats, get_rankings, get_all_rooms_students,
                     get_merchants, add_merchant)
from core.buzzer import play_waiting, play_victory
from core import camera

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in [cfg.TRIG, cfg.SERVO_L, cfg.SERVO_R, cfg.BUZZER,
            cfg.LED_L_GREEN, cfg.LED_L_RED, cfg.LED_R_GREEN, cfg.LED_R_RED]:
    GPIO.setup(pin, GPIO.OUT)
    GPIO.output(pin, GPIO.LOW)
GPIO.setup(cfg.ECHO, GPIO.IN)
for gpio in cfg.BUTTONS.values():
    GPIO.setup(gpio, GPIO.IN, pull_up_down=GPIO.PUD_UP)

GPIO.output(cfg.LED_L_RED, GPIO.HIGH)
GPIO.output(cfg.LED_R_RED, GPIO.HIGH)

servo_l = GPIO.PWM(cfg.SERVO_L, 50)
servo_r = GPIO.PWM(cfg.SERVO_R, 50)
servo_l.start(0)
servo_r.start(0)
doors_init(servo_l, servo_r)
init_db()

app = Flask(__name__)
app.secret_key = 'heliaris-v1.1-secret'

def _html(name):
    return open(os.path.join(os.path.dirname(__file__), 'html', name)).read()

def _require(role=None):
    acc = session.get('account')
    if not acc:
        return redirect('/login')
    if role and acc['role'] != role:
        return redirect('/login')
    return None

@app.route('/')
def index():
    acc = session.get('account')
    if not acc:
        return redirect('/login')
    if acc['role'] == 'admin':
        return redirect('/admin-mobile')
    if acc['role'] == 'student':
        return redirect('/student')
    if acc['role'] == 'delivery':
        return redirect('/delivery')
    return redirect('/login')

@app.route('/login')
def login_page():
    return _html('login.html')

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

@app.route('/api/status')
def api_status():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(cfg.state)

@app.route('/api/videos/clear', methods=['POST'])
def clear_videos():
    pattern = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'video', '**', '*.avi')
    for f in glob.glob(pattern, recursive=True):
        os.remove(f)
    return jsonify({"ok": True})

@app.route('/api/door/<side>', methods=['POST'])
def api_door(side):
    if side not in ('left', 'right'):
        return jsonify({"error": "invalid"}), 400
    if cfg.state[f"door_{side}"] == "open":
        return jsonify({"error": "already open"}), 400
    threading.Thread(target=open_door, args=(side, 'delivery'), daemon=True).start()
    return jsonify({"ok": True})

@app.route('/api/led/<side>/<color>/<action>', methods=['POST'])
def api_led(side, color, action):
    if side not in ('left', 'right') or color not in ('green', 'red') or action not in ('on', 'off'):
        return jsonify({"error": "invalid"}), 400
    green_on = (color == 'green' and action == 'on') or (color == 'red' and action == 'off')
    set_led(side, green_on)
    return jsonify({"ok": True})

@app.route('/api/button/<int:btn_num>', methods=['POST'])
def api_button(btn_num):
    if btn_num not in cfg.BUTTON_ROOMS:
        return jsonify({"error": "invalid"}), 400
    room = cfg.BUTTON_ROOMS[btn_num]
    side = cfg.ROOM_SIDE[room]
    cfg.state["last_event"] = f"[Web] 按鈕{btn_num} ({room}) 觸發"
    threading.Thread(target=open_door, args=(side, 'delivery'), daemon=True).start()
    return jsonify({"ok": True, "room": room, "side": side})

@app.route('/api/students')
def api_students():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_all_students())

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
    side = cfg.ROOM_SIDE.get(room)
    cfg.state["last_event"] = f"學生 {acc['name']} ({room}) 開箱"
    def task():
        open_door(side, 'student')
        pickup_order(pending['id'], sid)
    threading.Thread(target=task, daemon=True).start()
    return jsonify({"ok": True, "room": room, "side": side})

@app.route('/api/my-orders')
def api_my_orders():
    acc = session.get('account')
    if not acc or acc['role'] != 'student':
        return jsonify({"error": "unauthorized"}), 401
    pending = get_pending_order(acc['id'])
    return jsonify({
        "orders": get_my_orders(acc['id']),
        "points": get_points(acc['id']),
        "pending": pending,
        "name": acc['name'],
        "room": acc['room'],
    })

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
    side = cfg.ROOM_SIDE.get(room)
    oid = add_order(sid, room, merchant)
    cfg.state["last_event"] = f"外送員送達 {room} ({sid})"
    threading.Thread(target=open_door, args=(side, 'delivery'), daemon=True).start()
    return jsonify({"ok": True, "order_id": oid, "room": room, "side": side})

@app.route('/admin')
def admin_pc_page():
    r = _require('admin')
    return r if r else _html('index.html')

@app.route('/api/merchants', methods=['GET'])
def api_merchants_get():
    return jsonify(get_merchants())

@app.route('/api/merchants', methods=['POST'])
def api_merchants_post():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    category = data.get('category', '').strip()
    if not name:
        return jsonify({"error": "請輸入店家名稱"}), 400
    add_merchant(name, category)
    return jsonify({"ok": True})

@app.route('/api/rankings')
def api_rankings():
    month = request.args.get('month')
    return jsonify(get_rankings(month))

@app.route('/api/room-stats')
def api_room_stats():
    r = _require('admin')
    if r: return jsonify({"error": "unauthorized"}), 401
    return jsonify(get_room_monthly_stats())

@app.route('/stream')
def stream():
    def gen():
        while True:
            with cfg.frame_lock:
                data = cfg.latest_frame
            if data:
                yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + data + b'\r\n'
                time.sleep(1 / 20)  # 限制 20fps，避免 CPU 過載
            else:
                time.sleep(0.1)
    return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

sensor_start()
print("系統啟動 | http://10.164.207.88:8080 | Ctrl+C 停止")

try:
    app.run(host="0.0.0.0", port=8080, threaded=True)
except KeyboardInterrupt:
    pass
finally:
    sensor_stop()
    if camera.is_recording():
        camera.stop()
    servo_l.stop()
    servo_r.stop()
    del servo_l, servo_r
    for pin in [cfg.LED_L_GREEN, cfg.LED_L_RED, cfg.LED_R_GREEN, cfg.LED_R_RED]:
        GPIO.output(pin, GPIO.LOW)
    try:
        GPIO.cleanup()
        print("GPIO cleaned up.")
    except (KeyboardInterrupt, Exception):
        pass
