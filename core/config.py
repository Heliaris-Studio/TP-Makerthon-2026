import threading

# GPIO Pins
TRIG        = 20
ECHO        = 21
BUTTONS     = {1: 5, 2: 16, 3: 12, 4: 25}
BUTTON_ROOMS = {1: 'B301', 2: 'B302', 3: 'B405', 4: 'B406'}
SERVO_L     = 23
SERVO_R     = 24
LED_L_GREEN = 26
LED_L_RED   = 13
LED_R_GREEN = 19
LED_R_RED   = 6
BUZZER      = 22
THRESHOLD   = 15
SEGMENT_SEC = 60

ROOM_SIDE = {
    'B301': 'left',
    'B302': 'left',
    'B405': 'right',
    'B406': 'right',
}

# Shared runtime state
state = {
    "distance": None,
    "recording": False,
    "door_left": "closed",
    "door_right": "closed",
    "led_l_green": False,
    "led_l_red": True,
    "led_r_green": False,
    "led_r_red": True,
    "last_event": "",
}

latest_frame = b""
frame_lock   = threading.Lock()
door_lock    = threading.Lock()
