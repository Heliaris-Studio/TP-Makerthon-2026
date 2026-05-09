#!/usr/bin/env python3
import os
import glob
import time
import threading
import RPi.GPIO as GPIO
from flask import Flask, jsonify, Response, request
import core.config as cfg
from core.doors import init as doors_init, open_door, set_led
from core.sensor import start as sensor_start, stop as sensor_stop
from core.db import init_db, get_all_students, get_room_by_student
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

@app.route('/')
def index():
    return open(os.path.join(os.path.dirname(__file__), 'html', 'index.html')).read()

@app.route('/api/status')
def api_status():
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
    return jsonify(get_all_students())

@app.route('/api/open_by_student', methods=['POST'])
def api_open_by_student():
    data = request.get_json(silent=True) or {}
    sid = data.get('student_id', '').strip()
    room = get_room_by_student(sid)
    if not room:
        return jsonify({"error": "學號不存在"}), 404
    side = cfg.ROOM_SIDE.get(room)
    cfg.state["last_event"] = f"學生 {sid} ({room}) 開箱"
    threading.Thread(target=open_door, args=(side, 'student'), daemon=True).start()
    return jsonify({"ok": True, "room": room, "side": side})

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
