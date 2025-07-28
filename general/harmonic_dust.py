import time
import random
import logging
import sys
import threading
import math
import gc
import ctypes
import msvcrt
import os
import json
import win32api

# ─── Global State ─────────────────────────────────────────────────────────────
running = False
click_count = 0
click_thread = None

session_stats = {
    'total_harp_clicks': 0,
    'total_moves': 0,
    'total_breaks': 0,
    'session_start': None
}

# ─── Logging Configuration ────────────────────────────────────────────────────
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',
        'INFO': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[35m'
    }
    RESET = '\033[0m'
    def format(self, record):
        color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# ─── Configuration ────────────────────────────────────────────────────────────
START_STOP_KEY           = '`'
EXIT_KEY                 = '~'
CALIBRATION_KEY          = 'c'
REGION_FILE              = 'harp-region.json'
MIN_CLICK_INTERVAL       = 10      # seconds
MAX_CLICK_INTERVAL       = 20      # seconds
INITIAL_DELAY_SEC        = 10      # seconds before first click
PROGRESS_UPDATE_INTERVAL = 120     # for long waits
SHOW_DETAILED_PROGRESS   = False
FORCE_GARBAGE_COLLECTION = True
PRINT_STATS_INTERVAL     = 5       # print stats every N clicks

# ─── Native Windows Click via SendInput ───────────────────────────────────────
PUL = ctypes.POINTER(ctypes.c_ulong)
class MouseInput(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]
class Input_I(ctypes.Union):
    _fields_ = [("mi", MouseInput)]
class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004

def send_native_click(x=None, y=None):
    if x is not None and y is not None:
        ctypes.windll.user32.SetCursorPos(int(x), int(y))
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    cmd = Input(ctypes.c_ulong(0), ii_)
    ctypes.windll.user32.SendInput(1, ctypes.pointer(cmd), ctypes.sizeof(cmd))
    time.sleep(0.01)
    ii_.mi.dwFlags = MOUSEEVENTF_LEFTUP
    ctypes.windll.user32.SendInput(1, ctypes.pointer(cmd), ctypes.sizeof(cmd))

def set_mouse_position(x, y):
    ctypes.windll.user32.SetCursorPos(int(x), int(y))

def get_current_mouse_position():
    return win32api.GetCursorPos()

# ─── Enhanced Human-like Movement ─────────────────────────────────────────────
def bezier_curve(t, p0, p1, p2, p3):
    return ((1-t)**3 * p0 +
            3*(1-t)**2 * t * p1 +
            3*(1-t) * t**2 * p2 +
            t**3 * p3)

def ease_in_out_cubic(t):
    return 4*t*t*t if t < 0.5 else 1 - pow(-2*t + 2, 3) / 2

def ease_out_quad(t):
    return 1 - (1 - t)*(1 - t)

def generate_curve_points(sx, sy, ex, ey, intensity=0.3):
    dx, dy = ex-sx, ey-sy
    dist = math.hypot(dx, dy)
    if dist < 10:
        return None
    perp_x, perp_y = -dy/dist, dx/dist
    offset = random.uniform(-dist * intensity, dist * intensity)
    c1 = (sx + dx*0.25 + perp_x * offset*0.5,
          sy + dy*0.25 + perp_y * offset*0.5)
    c2 = (sx + dx*0.75 + perp_x * offset,
          sy + dy*0.75 + perp_y * offset)
    return {'p0': (sx, sy), 'p1': c1, 'p2': c2, 'p3': (ex, ey)}

def add_distraction_movement():
    if random.random() > 0.08:
        return
    cx, cy = get_current_mouse_position()
    dx = cx + random.randint(-400, 400)
    dy = cy + random.randint(-200, 200)
    dx = max(0, min(3600, dx)); dy = max(0, min(2000, dy))
    logger.debug(f"🎯 Distraction to ({dx:.0f}, {dy:.0f})")
    simple_move_to(dx, dy, speed_multiplier=1.5)
    time.sleep(random.uniform(0.1, 0.4))

def simple_move_to(tx, ty, speed_multiplier=1.0):
    sx, sy = get_current_mouse_position()
    dist = math.hypot(tx-sx, ty-sy)
    if dist < 2:
        return
    steps = int(max(5, min(15, dist / (4 * speed_multiplier))))
    for i in range(steps):
        if not running: break
        t = (i+1)/steps
        t_e = ease_out_quad(t)
        cx = sx + (tx-sx)*t_e + random.uniform(- (1-t)*0.3, (1-t)*0.3)
        cy = sy + (ty-sy)*t_e + random.uniform(- (1-t)*0.3, (1-t)*0.3)
        set_mouse_position(cx, cy)
        time.sleep(random.uniform(0.005, 0.012)/speed_multiplier)

def human_move(tx, ty):
    global session_stats
    sx, sy = get_current_mouse_position()
    dist = math.hypot(tx-sx, ty-sy)
    if dist < 3:
        return
    add_distraction_movement()
    sx, sy = get_current_mouse_position()
    dist = math.hypot(tx-sx, ty-sy)
    logger.debug(f"🎯 Move from ({sx:.0f},{sy:.0f}) to ({tx},{ty}) – {dist:.0f}px")
    overshoot = random.random() < 0.15 and dist>30
    if overshoot:
        od = random.uniform(5,15)
        ang = math.atan2(ty-sy, tx-sx)
        txo = tx + od*math.cos(ang)
        tyo = ty + od*math.sin(ang)
        logger.debug(f"🎯 Overshoot to ({txo:.0f},{tyo:.0f})")
        tx, ty = txo, tyo
    use_curve = dist>50 and random.random()<0.7
    steps = int(max(10, min(40, dist/2)))
    if use_curve:
        pts = generate_curve_points(sx, sy, tx, ty)
        if pts:
            move_along_curve(pts, steps)
        else:
            move_straight_enhanced(sx, sy, tx, ty, steps)
    else:
        move_straight_enhanced(sx, sy, tx, ty, steps)
    if overshoot and running:
        time.sleep(random.uniform(0.05,0.15))
        cx, cy = get_current_mouse_position()
        move_straight_enhanced(cx, cy, tx, ty, random.randint(3,8))
    if random.random() < 0.4 and running:
        time.sleep(random.uniform(0.02,0.08))
        fx = tx + random.uniform(-1,1)
        fy = ty + random.uniform(-1,1)
        set_mouse_position(fx, fy)
        logger.debug(f"🔧 Micro-correction to ({fx:.0f},{fy:.0f})")
    session_stats['total_moves'] += 1
    time.sleep(random.uniform(0.08,0.2))

def move_along_curve(pts, steps):
    p0,p1,p2,p3 = pts['p0'], pts['p1'], pts['p2'], pts['p3']
    for i in range(steps):
        if not running: break
        t = (i+1)/steps
        if t<0.3:
            te = ease_in_out_cubic(t/0.3)*0.3
        elif t>0.7:
            te = 0.7 + ease_in_out_cubic((t-0.7)/0.3)*0.3
        else:
            te = t
        cx = bezier_curve(te, *[p[k] for k in (0,1,2,3)])
        cy = bezier_curve(te, *[p[k] for k in (0,1,2,3)])
        jitter = (1-t)*0.8
        cx += random.uniform(-jitter, jitter)
        cy += random.uniform(-jitter, jitter)
        set_mouse_position(cx, cy)
        if random.random()<0.25*(1-t):
            ht = random.uniform(0.02,0.08)
            logger.debug(f"⏸️ Hesitation {ht:.3f}s")
            time.sleep(ht)
        time.sleep(random.uniform(0.008,0.018)*(1 - abs(te-0.5)*0.4))

def move_straight_enhanced(sx, sy, tx, ty, steps):
    for i in range(steps):
        if not running: break
        t = (i+1)/steps
        te = ease_in_out_cubic(t)
        cx = sx + (tx-sx)*te + random.uniform(- (1-t)*0.7, (1-t)*0.7)
        cy = sy + (ty-sy)*te + random.uniform(- (1-t)*0.7, (1-t)*0.7)
        trem_x = math.sin(t*20)*0.1*(1-t)*0.7
        trem_y = math.cos(t*25)*0.1*(1-t)*0.7
        set_mouse_position(cx+trem_x, cy+trem_y)
        if random.random()<0.25*(1-t):
            time.sleep(random.uniform(0.015,0.06))
        time.sleep(random.uniform(0.006,0.016))

# ─── Region Calibration ───────────────────────────────────────────────────────
def calibrate_region():
    print("Move to TOP‑LEFT of harp region, press Enter…")
    while True:
        if msvcrt.kbhit() and msvcrt.getch()==b'\r':
            x1,y1 = win32api.GetCursorPos()
            break
    print("Move to BOT‑RIGHT of harp region, press Enter…")
    while True:
        if msvcrt.kbhit() and msvcrt.getch()==b'\r':
            x2,y2 = win32api.GetCursorPos()
            break
    region = (x1,y1,x2,y2)
    with open(REGION_FILE,'w') as f:
        json.dump({'HARP_REGION': region}, f)
    print(f"Harp region saved: {region}")
    return region

def load_region():
    if os.path.exists(REGION_FILE):
        with open(REGION_FILE,'r') as f:
            return tuple(json.load(f)['HARP_REGION'])
    else:
        return calibrate_region()

HARP_REGION = load_region()

def random_target_within(region):
    x1,y1,x2,y2 = region
    if random.random()<0.7:
        cx, cy = (x1+x2)/2, (y1+y2)/2
        return (
            int(cx + random.uniform(-8,8)),
            int(cy + random.uniform(-8,8))
        )
    else:
        return (
            random.randint(x1+4, x2-4),
            random.randint(y1+4, y2-4)
        )

# ─── Utilities ────────────────────────────────────────────────────────────────
def format_time(sec):
    h,m = divmod(int(sec),3600)
    m,s = divmod(m,60)
    if h: return f"{h}h {m}m {s}s"
    if m: return f"{m}m {s}s"
    return f"{s}s"

def print_stats():
    if session_stats['session_start']:
        elapsed = time.time() - session_stats['session_start']
        total = session_stats['total_harp_clicks']
        cpm = (total/elapsed)*60 if elapsed>0 else 0
        logger.info("="*40)
        logger.info("📊 SESSION STATISTICS")
        logger.info("="*40)
        logger.info(f"🎵 Harp Clicks: {total}")
        logger.info(f"📍 Total Moves: {session_stats['total_moves']}")
        logger.info(f"☕ Breaks: {session_stats['total_breaks']}")
        logger.info(f"⏱️ Time: {format_time(elapsed)}")
        logger.info(f"⚡ Clicks/Min: {cpm:.1f}")
        logger.info(f"🎯 Region: {HARP_REGION}")
        logger.info("="*40)

# ─── Core Click Function ─────────────────────────────────────────────────────
def click_harp():
    global click_count, session_stats
    logger.info("🎵 Clicking harp…")
    x,y = random_target_within(HARP_REGION)
    logger.info(f"🎯 Moving to: ({x},{y})")
    human_move(x, y)
    if not running:
        return False
    cx, cy = get_current_mouse_position()
    set_mouse_position(cx + random.uniform(-0.8,0.8), cy + random.uniform(-0.8,0.8))
    time.sleep(random.uniform(0.03,0.12))
    send_native_click(*get_current_mouse_position())
    click_count += 1
    session_stats['total_harp_clicks'] += 1
    logger.info(f"✅ Click #{click_count} at {get_current_mouse_position()}")
    return True

# ─── Smart Wait ───────────────────────────────────────────────────────────────
def smart_wait(wait_time, desc="next action"):
    if wait_time <= 30:
        end = time.time() + wait_time
        while running and time.time() < end:
            time.sleep(min(5, wait_time))
        return
    logger.info(f"⏰ Waiting {wait_time:.1f}s for {desc}…")
    end = time.time() + wait_time
    last = time.time()
    while running and time.time() < end:
        rem = end - time.time()
        now = time.time()
        if SHOW_DETAILED_PROGRESS and now - last >= PROGRESS_UPDATE_INTERVAL and rem>60:
            logger.info(f"⏳ {int(rem//60)}m remaining for {desc}…")
            last = now
        if rem>120:
            time.sleep(30)
        elif rem>60:
            time.sleep(15)
        elif rem>30:
            time.sleep(10)
        else:
            time.sleep(2)

# ─── Click Loop ────────────────────────────────────────────────────────────────
def click_loop():
    logger.info("🚀 Entering click loop…")
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC}s to switch windows")
    for i in range(INITIAL_DELAY_SEC, 0, -1):
        if not running:
            return
        logger.info(f"⏳ Starting in {i}s…")
        time.sleep(1)
    logger.info("🎯 Starting automation now!")
    while running:
        try:
            if not click_harp():
                break
            if click_count % PRINT_STATS_INTERVAL == 0:
                print_stats()
                if FORCE_GARBAGE_COLLECTION:
                    gc.collect()
            interval = random.uniform(MIN_CLICK_INTERVAL, MAX_CLICK_INTERVAL)
            smart_wait(interval, "next harp click")
        except Exception as e:
            logger.error(f"❌ Error in loop: {e}")
            break
    logger.info("⏸️  Click loop stopped.")

# ─── Keyboard Monitor ─────────────────────────────────────────────────────────
def handle_start_stop():
    global running, click_thread, session_stats
    if not running:
        running = True
        session_stats['session_start'] = time.time()
        click_thread = threading.Thread(target=click_loop, daemon=True)
        click_thread.start()
        logger.info("▶️  Automation STARTED")
    else:
        running = False
        click_thread.join(timeout=5)
        logger.info("⏸️  Automation PAUSED")
        print_stats()

def handle_exit():
    global running
    logger.info("🛑 EXITING…")
    running = False
    sys.exit(0)

def handle_calibration():
    logger.info("🎯 CALIBRATION MODE")
    global HARP_REGION
    HARP_REGION = calibrate_region()

def keyboard_monitor():
    logger.info("⌨️  Press '`' to start/stop, '~' to exit, 'c' to calibrate")
    while True:
        if msvcrt.kbhit():
            key = msvcrt.getch().decode('utf-8').lower()
            if key == START_STOP_KEY:
                handle_start_stop()
                time.sleep(0.3)
            elif key == EXIT_KEY:
                handle_exit()
            elif key == CALIBRATION_KEY:
                handle_calibration()
                time.sleep(0.3)
        else:
            time.sleep(0.05)

# ─── Main Entry ───────────────────────────────────────────────────────────────
def main():
    logger.info("🎮 Anti‑Bot Harp Clicker Script")
    logger.info(f"🎯 Calibrated Harp Region: {HARP_REGION}")
    logger.info(f"⌨️  START/STOP: Press '{START_STOP_KEY}'")
    logger.info(f"⌨️  EXIT: Press '{EXIT_KEY}'")
    logger.info(f"🛠️  CALIBRATE: Press '{CALIBRATION_KEY}'")
    logger.info(f"⏳ Click interval: {MIN_CLICK_INTERVAL}-{MAX_CLICK_INTERVAL}s")
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC}s")
    logger.info("="*60)
    keyboard_monitor()

if __name__ == "__main__":
    main()