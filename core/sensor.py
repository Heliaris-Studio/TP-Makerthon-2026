import time
import threading
import RPi.GPIO as GPIO
import core.config as cfg
from core.camera import start as cam_start, stop as cam_stop, is_recording
from core.doors import open_door

_running = False


def _btn_callback(gpio):
    btn_num = next(n for n, g in cfg.BUTTONS.items() if g == gpio)
    room = cfg.BUTTON_ROOMS.get(btn_num)
    side = cfg.ROOM_SIDE.get(room, "left")
    cfg.state["last_event"] = f"按鈕{btn_num} ({room}) 按下"
    def task():
        time.sleep(0.05)   # 等 GPIO 訊號穩定即可
        open_door(side, buzzer_mode="delivery")
    threading.Thread(target=task, daemon=True).start()


def start():
    global _running
    _running = True
    for gpio in cfg.BUTTONS.values():
        GPIO.add_event_detect(gpio, GPIO.FALLING, callback=_btn_callback, bouncetime=300)

    def loop():
        close_count = 0   # 連續「距離 >= 閾值」計數，防止瞬間壞值關閉攝影機
        CLOSE_NEEDED = 4  # 需要連續 4 次 (約 1.2 秒) 才真正關閉
        while _running:
            try:
                dist = _measure()
                if dist is not None:
                    cfg.state["distance"] = round(dist, 1)
                    if dist < cfg.THRESHOLD:
                        close_count = 0
                        if not is_recording():
                            cam_start()
                    else:
                        close_count += 1
                        if close_count >= CLOSE_NEEDED and is_recording():
                            cam_stop()
                            close_count = 0
            except RuntimeError:
                break
            time.sleep(0.3)

    threading.Thread(target=loop, daemon=True).start()


def stop():
    global _running
    _running = False


def _measure():
    GPIO.output(cfg.TRIG, GPIO.HIGH)
    time.sleep(0.00001)
    GPIO.output(cfg.TRIG, GPIO.LOW)
    deadline = time.time() + 0.02
    while GPIO.input(cfg.ECHO) == GPIO.LOW:
        if time.time() > deadline:
            return None
    t0 = time.time()
    deadline = t0 + 0.02
    while GPIO.input(cfg.ECHO) == GPIO.HIGH:
        if time.time() > deadline:
            return None
    return (time.time() - t0) * 34300 / 2

