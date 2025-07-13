import time
import random
import logging
import sys
import threading
import math
import gc
import ctypes
from ctypes import windll, wintypes
import win32api
import win32con
import win32gui
import msvcrt
import os
import json

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
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
handler.flush = lambda: handler.stream.flush()
logger.addHandler(handler)

# ─── Configuration ────────────────────────────────────────────────────────────
START_STOP_KEY    = '`'
EXIT_KEY          = '~'
CALIBRATION_KEY   = 'c'

REGION_FILE = 'regions.json'

# ─── Calibration ──────────────────────────────────────────────────────────────
def calibrate_region(name):
    print(f"Move mouse to TOP-LEFT of {name} and press Enter...")
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b'\r':
            x1, y1 = win32api.GetCursorPos()
            break
    print(f"Move mouse to BOTTOM-RIGHT of {name} and press Enter...")
    while True:
        if msvcrt.kbhit() and msvcrt.getch() == b'\r':
            x2, y2 = win32api.GetCursorPos()
            break
    print(f"{name} region: ({x1}, {y1}, {x2}, {y2})")
    return (x1, y1, x2, y2)

def calibrate_all_regions():
    print("\n--- Calibration Mode ---")
    dung_hole = calibrate_region("Dung Hole")
    lemon_sour = calibrate_region("Lemon Sour")
    hole_in_one = calibrate_region("Hole in One")
    regions = {
        'DUNG_HOLE_REGION': dung_hole,
        'LEMON_SOUR_REGION': lemon_sour,
        'HOLE_IN_ONE_REGION': hole_in_one
    }
    with open(REGION_FILE, 'w') as f:
        json.dump(regions, f)
    print("Regions saved to regions.json!")
    return regions

def load_regions():
    if os.path.exists(REGION_FILE):
        with open(REGION_FILE, 'r') as f:
            return json.load(f)
    else:
        logger.warning("No region calibration found. Please calibrate (press 'c').")
        return calibrate_all_regions()

regions = load_regions()
DUNG_HOLE_REGION = tuple(regions['DUNG_HOLE_REGION'])
LEMON_SOUR_REGION = tuple(regions['LEMON_SOUR_REGION'])
HOLE_IN_ONE_REGION = tuple(regions['HOLE_IN_ONE_REGION'])

MIN_CLICKS_BEFORE_BREAK = 20
BREAK_MIN_SEC     = 5
BREAK_MAX_SEC     = 15
INITIAL_DELAY_SEC = 10

PROGRESS_UPDATE_INTERVAL = 120
SHOW_DETAILED_PROGRESS = False
FORCE_GARBAGE_COLLECTION = True

USE_HOLE_IN_ONE = False
COCKTAIL_INTERVAL_NORMAL = 10
COCKTAIL_INTERVAL_HOLE_IN_ONE = 4
DUNG_HOLE_DURATION_NORMAL = (79, 90)
DUNG_HOLE_DURATION_HOLE_IN_ONE = (242, 250)

ENABLE_CURVED_PATHS = True
ENABLE_OVERSHOOT = True
ENABLE_HESITATION = True
ENABLE_MICRO_CORRECTIONS = True
ENABLE_MOMENTUM = True
ENABLE_DISTRACTION_MOVES = True

CURVE_INTENSITY = 0.3
OVERSHOOT_CHANCE = 0.15
HESITATION_CHANCE = 0.25
DISTRACTION_CHANCE = 0.08
MICRO_CORRECTION_CHANCE = 0.4

# ─── Native Windows Mouse Click with ctypes/SendInput ─────────────────────────
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
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", Input_I)
    ]
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004

def send_native_click(x=None, y=None):
    if x is not None and y is not None:
        windll.user32.SetCursorPos(int(x), int(y))
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(0), ii_)
    windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))
    time.sleep(0.01)
    ii_.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(0), ii_)
    windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))

def set_mouse_position(x, y):
    windll.user32.SetCursorPos(int(x), int(y))

def get_current_mouse_position():
    return win32api.GetCursorPos()

# ─── Enhanced Human-like Movement System ───────────────────────────────────────
def bezier_curve(t, p0, p1, p2, p3):
    return ((1-t)**3 * p0 + 3*(1-t)**2*t * p1 + 3*(1-t)*t**2 * p2 + t**3 * p3)

def ease_in_out_cubic(t):
    return 4*t*t*t if t < 0.5 else 1-pow(-2*t+2, 3)/2

def ease_out_quad(t: float) -> float:
    return 1 - (1 - t) * (1 - t)

def generate_curve_points(start_x, start_y, end_x, end_y, curve_intensity=0.3):
    mid_x = (start_x + end_x) / 2
    mid_y = (start_y + end_y) / 2
    
    dx = end_x - start_x
    dy = end_y - start_y
    distance = math.sqrt(dx*dx + dy*dy)
    
    if distance < 10:
        return None
    
    perp_x = -dy / distance
    perp_y = dx / distance
    
    curve_offset = random.uniform(-distance * curve_intensity, distance * curve_intensity)
    
    control1_x = start_x + dx * 0.25 + perp_x * curve_offset * 0.5
    control1_y = start_y + dy * 0.25 + perp_y * curve_offset * 0.5
    control2_x = start_x + dx * 0.75 + perp_x * curve_offset
    control2_y = start_y + dy * 0.75 + perp_y * curve_offset
    
    return {
        'p0': (start_x, start_y),
        'p1': (control1_x, control1_y),
        'p2': (control2_x, control2_y),
        'p3': (end_x, end_y)
    }

def add_distraction_movement():
    if not ENABLE_DISTRACTION_MOVES or random.random() > DISTRACTION_CHANCE:
        return
    
    current_x, current_y = get_current_mouse_position()
    
    distraction_x = current_x + random.randint(-400, 400)
    distraction_y = current_y + random.randint(-200, 200)
    
    distraction_x = max(200, min(3600, distraction_x))
    distraction_y = max(200, min(2000, distraction_y))
    
    logger.debug(f"🎯 Distraction movement to ({distraction_x}, {distraction_y})")
    
    simple_move_to(distraction_x, distraction_y, speed_multiplier=1.5)
    
    time.sleep(random.uniform(0.1, 0.4))

def simple_move_to(to_x, to_y, speed_multiplier=1.0):
    start_x, start_y = get_current_mouse_position()
    distance = math.sqrt((to_x - start_x)**2 + (to_y - start_y)**2)
    
    if distance < 2:
        return
    
    steps = int(max(5, min(15, distance / (4 * speed_multiplier))))
    
    for i in range(steps):
        if not running:
            break
        
        t = (i + 1) / steps
        t_eased = ease_out_quad(t)
        
        cur_x = start_x + (to_x - start_x) * t_eased
        cur_y = start_y + (to_y - start_y) * t_eased
        
        jitter = (1 - t) * 0.3
        cur_x += random.uniform(-jitter, jitter)
        cur_y += random.uniform(-jitter, jitter)
        
        set_mouse_position(cur_x, cur_y)
        time.sleep(random.uniform(0.005, 0.012) / speed_multiplier)

def human_move(to_x: int, to_y: int):
    global session_stats
    start_x, start_y = get_current_mouse_position()
    distance = math.sqrt((to_x - start_x)**2 + (to_y - start_y)**2)

    if distance < 3:
        return
    
    add_distraction_movement()
    
    start_x, start_y = get_current_mouse_position()
    distance = math.sqrt((to_x - start_x)**2 + (to_y - start_y)**2)
    
    logger.debug(f"🎯 Enhanced move from ({start_x:.0f}, {start_y:.0f}) to ({to_x}, {to_y}) - Distance: {distance:.1f}px")
    
    use_curves = ENABLE_CURVED_PATHS and distance > 50 and random.random() < 0.7
    will_overshoot = ENABLE_OVERSHOOT and distance > 30 and random.random() < OVERSHOOT_CHANCE
    
    target_x, target_y = to_x, to_y
    if will_overshoot:
        overshoot_distance = random.uniform(5, 15)
        angle = math.atan2(to_y - start_y, to_x - start_x)
        target_x = to_x + overshoot_distance * math.cos(angle)
        target_y = to_y + overshoot_distance * math.sin(angle)
        logger.debug(f"🎯 Overshoot target: ({target_x:.0f}, {target_y:.0f})")
    
    steps = int(max(10, min(40, distance / 2)))
    
    if use_curves:
        curve_points = generate_curve_points(start_x, start_y, target_x, target_y, CURVE_INTENSITY)
        if curve_points:
            logger.debug("🏹 Using curved path")
            move_along_curve(curve_points, steps, distance)
        else:
            move_straight_enhanced(start_x, start_y, target_x, target_y, steps)
    else:
        move_straight_enhanced(start_x, start_y, target_x, target_y, steps)
    
    if will_overshoot and running:
        logger.debug("🎯 Correcting overshoot...")
        time.sleep(random.uniform(0.05, 0.15))
        current_pos = get_current_mouse_position()
        move_straight_enhanced(current_pos[0], current_pos[1], to_x, to_y, correction_steps)
    
    if ENABLE_MICRO_CORRECTIONS and random.random() < MICRO_CORRECTION_CHANCE and running:
        time.sleep(random.uniform(0.02, 0.08))
        final_x = to_x + random.uniform(-1, 1)
        final_y = to_y + random.uniform(-1, 1)
        set_mouse_position(final_x, final_y)
        logger.debug(f"🔧 Micro-correction to ({final_x:.0f}, {final_y:.0f})")
    
    session_stats['total_moves'] += 1
    
    time.sleep(random.uniform(0.08, 0.2))

def move_along_curve(curve_points, steps, distance):
    p0, p1, p2, p3 = curve_points['p0'], curve_points['p1'], curve_points['p2'], curve_points['p3']
    
    for i in range(steps):
        if not running:
            break
        
        t = (i + 1) / steps
        
        if t < 0.3:
            t_eased = ease_in_out_cubic(t / 0.3) * 0.3
        elif t > 0.7:
            t_eased = 0.7 + ease_in_out_cubic((t - 0.7) / 0.3) * 0.3
        else:
            t_eased = t
        
        cur_x = bezier_curve(t_eased, p0[0], p1[0], p2[0], p3[0])
        cur_y = bezier_curve(t_eased, p0[1], p1[1], p2[1], p3[1])
        
        jitter_strength = (1 - t) * 0.8
        cur_x += random.uniform(-jitter_strength, jitter_strength)
        cur_y += random.uniform(-jitter_strength, jitter_strength)
        
        set_mouse_position(cur_x, cur_y)
        
        base_sleep = random.uniform(0.008, 0.018)
        
        if ENABLE_HESITATION and random.random() < HESITATION_CHANCE * (1 - t):
            hesitation_time = random.uniform(0.02, 0.08)
            logger.debug(f"⏸️ Hesitation pause: {hesitation_time:.3f}s")
            time.sleep(hesitation_time)
        
        if ENABLE_MOMENTUM:
            momentum_factor = 1 - abs(t - 0.5) * 0.4
            base_sleep *= momentum_factor
        
        time.sleep(base_sleep)

def move_straight_enhanced(start_x, start_y, target_x, target_y, steps):
    for i in range(steps):
        if not running:
            break
        
        t = (i + 1) / steps
        t_eased = ease_in_out_cubic(t)
        
        cur_x = start_x + (target_x - start_x) * t_eased
        cur_y = start_y + (target_y - start_y) * t_eased
        
        jitter_strength = (1 - t) * 0.7
        noise_x = random.uniform(-jitter_strength, jitter_strength)
        noise_y = random.uniform(-jitter_strength, jitter_strength)
        
        tremor_x = math.sin(t * 20) * 0.1 * jitter_strength
        tremor_y = math.cos(t * 25) * 0.1 * jitter_strength
        
        cur_x += noise_x + tremor_x
        cur_y += noise_y + tremor_y
        
        set_mouse_position(cur_x, cur_y)
        
        base_sleep = random.uniform(0.006, 0.016)
        
        if ENABLE_HESITATION and random.random() < HESITATION_CHANCE * (1 - t):
            hesitation_time = random.uniform(0.015, 0.06)
            time.sleep(hesitation_time)
        
        time.sleep(base_sleep)

def random_target_within(region):
    x_min, y_min, x_max, y_max = region
    
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    
    if random.random() < 0.7:
        offset_x = random.uniform(-8, 8)
        offset_y = random.uniform(-8, 8)
        x = int(center_x + offset_x)
        y = int(center_y + offset_y)
    else:
        inset = 4
        x = random.randint(x_min + inset, x_max - inset)
        y = random.randint(y_min + inset, y_max - inset)
    
    x = max(x_min + 2, min(x_max - 2, x))
    y = max(y_min + 2, min(y_max - 2, y))
    
    return x, y

def format_time(seconds):
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_current_settings():
    if USE_HOLE_IN_ONE:
        return {
            'cocktail_interval': COCKTAIL_INTERVAL_HOLE_IN_ONE,
            'dung_hole_duration': DUNG_HOLE_DURATION_HOLE_IN_ONE,
            'mode': 'Hole in One Mode'
        }
    else:
        return {
            'cocktail_interval': COCKTAIL_INTERVAL_NORMAL,
            'dung_hole_duration': DUNG_HOLE_DURATION_NORMAL,
            'mode': 'Normal Mode'
        }

def print_stats():
    if session_stats['session_start']:
        elapsed = time.time() - session_stats['session_start']
        total_clicks = session_stats['total_dung_clicks'] + session_stats['total_lemon_clicks'] + session_stats['total_hole_in_one_clicks']
        clicks_per_min = (total_clicks / elapsed) * 60 if elapsed > 0 else 0
        settings = get_current_settings()
        
        logger.info("=" * 60)
        logger.info("📊 SESSION STATISTICS")
        logger.info("=" * 60)
        logger.info(f"🕳️  Dung Hole Clicks: {session_stats['total_dung_clicks']}")
        logger.info(f"🍋 Lemon Sour Clicks: {session_stats['total_lemon_clicks']}")
        if USE_HOLE_IN_ONE:
            logger.info(f"🏌️  Hole in One Clicks: {session_stats['total_hole_in_one_clicks']}")
        logger.info(f"📍 Total Moves: {session_stats['total_moves']}")
        logger.info(f"☕ Total Breaks: {session_stats['total_breaks']}")
        logger.info(f"🔄 Cocktail Cycles: {session_stats['cocktail_cycles']}")
        logger.info(f"⏱️  Session Time: {format_time(elapsed)}")
        logger.info(f"⚡ Clicks/Min: {clicks_per_min:.1f}")
        logger.info(f"🎮 Mode: {settings['mode']}")
        logger.info(f"🕳️  Dung Hole Region: {DUNG_HOLE_REGION}")
        logger.info(f"🍋 Lemon Sour Region: {LEMON_SOUR_REGION}")
        if USE_HOLE_IN_ONE:
            logger.info(f"🏌️  Hole in One Region: {HOLE_IN_ONE_REGION}")
        logger.info("=" * 60)

def click_hole_in_one():
    global session_stats
    
    logger.info("🏌️  Clicking Hole in One cocktail...")
    tx, ty = random_target_within(HOLE_IN_ONE_REGION)
    logger.info(f"🎯 Moving to Hole in One: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    current_x, current_y = get_current_mouse_position()
    set_mouse_position(current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    time.sleep(random.uniform(0.03, 0.12))
    
    send_native_click(*get_current_mouse_position())
    session_stats['total_hole_in_one_clicks'] += 1
    
    logger.info(f"✅ Hole in One click #{session_stats['total_hole_in_one_clicks']} completed at {get_current_mouse_position()}")
    return True

def click_lemon_sour():
    global session_stats
    
    logger.info("🍋 Clicking Lemon Sour cocktail...")
    tx, ty = random_target_within(LEMON_SOUR_REGION)
    logger.info(f"🎯 Moving to Lemon Sour: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    current_x, current_y = get_current_mouse_position()
    set_mouse_position(current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    time.sleep(random.uniform(0.03, 0.12))
    
    send_native_click(*get_current_mouse_position())
    session_stats['total_lemon_clicks'] += 1
    
    logger.info(f"✅ Lemon Sour click #{session_stats['total_lemon_clicks']} completed at {get_current_mouse_position()}")
    return True

def click_cocktails():
    logger.info("🍹 Starting cocktail sequence...")
    
    if USE_HOLE_IN_ONE:
        if not click_hole_in_one():
            return False
            
        delay = random.uniform(2.5, 7.5)
        logger.info(f"⏳ Waiting {delay:.1f}s between cocktails...")
        end_time = time.time() + delay
        while running and time.time() < end_time:
            time.sleep(0.5)
        
        if not running:
            return False
            
        if not click_lemon_sour():
            return False
    else:
        if not click_lemon_sour():
            return False
    
    logger.info("🍹 Cocktail sequence completed!")
    return True

def click_dung_hole():
    global click_count, session_stats
    
    logger.info("🕳️  Clicking dung hole...")
    tx, ty = random_target_within(DUNG_HOLE_REGION)
    logger.info(f"🎯 Moving to dung hole: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    current_x, current_y = get_current_mouse_position()
    set_mouse_position(current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    time.sleep(random.uniform(0.03, 0.12))
    
    send_native_click(*get_current_mouse_position())
    click_count += 1
    session_stats['total_dung_clicks'] += 1
    
    logger.info(f"✅ Dung hole click #{click_count} completed at {get_current_mouse_position()}")
    return True

def smart_wait(wait_time, action_description="next action"):
    if wait_time <= 30:
        end_time = time.time() + wait_time
        while running and time.time() < end_time:
            time.sleep(min(5, wait_time))
        return
    
    logger.info(f"⏰ Waiting {wait_time:.1f}s until {action_description}...")
    
    end_time = time.time() + wait_time
    last_progress_time = time.time()
    
    while running and time.time() < end_time:
        remaining = end_time - time.time()
        current_time = time.time()
        
        if (SHOW_DETAILED_PROGRESS and 
            current_time - last_progress_time >= PROGRESS_UPDATE_INTERVAL and 
            remaining > 60):
            
            minutes = int(remaining // 60)
            logger.info(f"⏳ {minutes}m remaining until {action_description}...")
            logger.handlers[0].flush()
            last_progress_time = current_time
        
        if remaining > 120:
            time.sleep(30)
        elif remaining > 60:
            time.sleep(15)
        elif remaining > 30:
            time.sleep(10)
        else:
            time.sleep(2)

def click_loop():
    global click_count, running, session_stats

    settings = get_current_settings()
    
    logger.info("🚀 Entering click loop. Press '`' to stop, '~' to exit.")
    logger.info(f"🎮 Mode: {settings['mode']}")
    logger.info(f"🕳️  Dung Hole Region: {DUNG_HOLE_REGION}")
    logger.info(f"🍋 Lemon Sour Region: {LEMON_SOUR_REGION}")
    if USE_HOLE_IN_ONE:
        logger.info(f"🏌️  Hole in One Region: {HOLE_IN_ONE_REGION}")
    
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC} seconds to switch screens...")
    for i in range(INITIAL_DELAY_SEC, 0, -1):
        if not running:
            logger.info("⏹️  Startup cancelled.")
            return
        logger.info(f"⏳ Starting in {i} seconds...")
        time.sleep(1)
    
    logger.info("🎯 Starting automation NOW!")
    
    logger.info("🍹 Starting with cocktail sequence...")
    if not click_cocktails():
        return
    
    smart_wait(random.uniform(2.5, 7.5), "first dung hole click")
    
    dung_hole_count = 0
    
    while running:
        try:
            if not click_dung_hole():
                break
            
            dung_hole_count += 1
            
            if dung_hole_count % 5 == 0:
                print_stats()
                if FORCE_GARBAGE_COLLECTION:
                    gc.collect()
            
            min_wait, max_wait = settings['dung_hole_duration']
            interval = random.uniform(min_wait, max_wait)
            
            if USE_HOLE_IN_ONE:
                smart_wait(interval, "character to exit dung hole (Hole in One mode)")
            else:
                smart_wait(interval, "character to exit dung hole")
            
            if dung_hole_count % settings['cocktail_interval'] == 0:
                session_stats['cocktail_cycles'] += 1
                logger.info(f"🔄 Cycle #{session_stats['cocktail_cycles']}: Time for cocktail sequence!")
                
                if not click_cocktails():
                    break
                
                smart_wait(random.uniform(2.5, 7.5), "next dung hole click")
            
            if click_count % MIN_CLICKS_BEFORE_BREAK == 0:
                break_duration = random.uniform(BREAK_MIN_SEC, BREAK_MAX_SEC)
                session_stats['total_breaks'] += 1
                logger.info(f"☕ Taking break #{session_stats['total_breaks']} for {break_duration:.1f}s to stretch...")
                
                smart_wait(break_duration, "break completion")
                
                if running:
                    logger.info("🔄 Break finished, resuming automation...")
                    
        except Exception as e:
            logger.error(f"❌ Error in click loop: {e}")
            break
    
    logger.info("⏸️  Click loop stopped.")

# ─── Console Keyboard Monitoring ───────────────────────────────────────────────

def keyboard_monitor():
    """Console-based keyboard monitoring using msvcrt"""
    logger.info("⌨️  Keyboard monitoring started. Press '`' to start/stop, '~' to exit, 'c' for calibration")
    logger.info("💡 Note: Make sure this console window is focused for key detection")
    
    try:
        while True:
            if msvcrt.kbhit():
                key = msvcrt.getch().decode('utf-8').lower()
                
                if key == '`':
                    handle_start_stop()
                    time.sleep(0.3)  # Prevent multiple triggers
                elif key == '~':
                    handle_exit()
                    break
                elif key == 'c':
                    handle_calibration()
                    time.sleep(0.3)  # Prevent multiple triggers
            else:
                time.sleep(0.05)  # Short sleep when no key is pressed
                
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Error in keyboard monitor: {e}")

def handle_start_stop():
    global running, click_thread, session_stats
    if not running:
        running = True
        session_stats['session_start'] = time.time()
        logger.info("▶️  AUTOMATION STARTED")
        logger.info(f"🎮 Controls: Press '`' to stop, '~' to exit")
        click_thread = threading.Thread(target=click_loop, daemon=True)
        click_thread.start()
    else:
        running = False
        logger.info("⏸️  AUTOMATION PAUSED")
        if click_thread and click_thread.is_alive():
            logger.info("⏳ Waiting for current action to complete...")
            click_thread.join(timeout=5)
        print_stats()
        logger.info(f"🎮 Press '`' to resume, '~' to exit")

def handle_exit():
    global running, click_thread
    logger.info("🛑 EXIT REQUESTED")
    running = False
    if click_thread and click_thread.is_alive():
        logger.info("⏳ Waiting for automation to stop...")
        click_thread.join(timeout=5)
    print_stats()
    logger.info("👋 Goodbye!")
    sys.exit(0)

def handle_calibration():
    logger.info("🎯 CALIBRATION MODE")
    logger.info("📍 Move your mouse to the target location and press 'c' to get coordinates")
    pos = get_mouse_position()
    logger.info(f"📏 DPI Scale: {DPI_SCALE:.2f}x")
    logger.info(f"🔄 To update coordinates, modify BASE_*_REGION values in the script")

def main():
    settings = get_current_settings()
    
    logger.info("🎮 Enhanced Anti-Bot Mouse Automation Script")
    logger.info("=" * 60)
    logger.info(f"🎮 Mode: {settings['mode']}")
    logger.info(f"⌨️  START/STOP: Press '`' (backtick)")
    logger.info(f"⌨️  EXIT: Press '~' (tilde)")
    logger.info(f"🎯 CALIBRATION: Press 'c' to get mouse coordinates")
    logger.info("─" * 60)
    logger.info("🖥️  DISPLAY CONFIGURATION:")
    logger.info(f"🖥️  Calibrated Dung Hole Region: {DUNG_HOLE_REGION}")
    logger.info(f"🖥️  Calibrated Lemon Sour Region: {LEMON_SOUR_REGION}")
    logger.info(f"🖥️  Calibrated Hole in One Region: {HOLE_IN_ONE_REGION}")
    logger.info("─" * 60)
    logger.info("🤖 ANTI-BOT DETECTION FEATURES:")
    logger.info(f"🏹 Curved Paths: {'✅ Enabled' if ENABLE_CURVED_PATHS else '❌ Disabled'}")
    logger.info(f"🎯 Overshoot Correction: {'✅ Enabled' if ENABLE_OVERSHOOT else '❌ Disabled'} ({OVERSHOOT_CHANCE*100:.0f}% chance)")
    logger.info(f"⏸️ Hesitation Pauses: {'✅ Enabled' if ENABLE_HESITATION else '❌ Disabled'} ({HESITATION_CHANCE*100:.0f}% chance)")
    logger.info(f"🔧 Micro Corrections: {'✅ Enabled' if ENABLE_MICRO_CORRECTIONS else '❌ Disabled'} ({MICRO_CORRECTION_CHANCE*100:.0f}% chance)")
    logger.info(f"🌊 Momentum Simulation: {'✅ Enabled' if ENABLE_MOMENTUM else '❌ Disabled'}")
    logger.info(f"👀 Distraction Moves: {'✅ Enabled' if ENABLE_DISTRACTION_MOVES else '❌ Disabled'} ({DISTRACTION_CHANCE*100:.0f}% chance)")
    logger.info(f"🎨 Curve Intensity: {CURVE_INTENSITY*100:.0f}%")
    logger.info("─" * 60)
    
    if USE_HOLE_IN_ONE:
        logger.info(f"⏰ Dung Hole Duration: {settings['dung_hole_duration'][0]//60}:{settings['dung_hole_duration'][0]%60:02d}-{settings['dung_hole_duration'][1]//60}:{settings['dung_hole_duration'][1]%60:02d} minutes")
        logger.info(f"🍹 Cocktail Sequence: Hole in One → Lemon Sour")
    else:
        logger.info(f"⏰ Dung Hole Duration: {settings['dung_hole_duration'][0]}-{settings['dung_hole_duration'][1]} seconds")
        logger.info(f"🍹 Cocktail Sequence: Lemon Sour only")
    
    logger.info(f"🔄 Cocktail Interval: Every {settings['cocktail_interval']} dung hole clicks")
    logger.info(f"☕ Break Every: {MIN_CLICKS_BEFORE_BREAK} clicks")
    logger.info(f"⏳ Initial Delay: {INITIAL_DELAY_SEC} seconds")
    logger.info(f"📊 Progress Updates: Every {PROGRESS_UPDATE_INTERVAL}s for long waits")
    logger.info("=" * 60)
    
    if USE_HOLE_IN_ONE:
        logger.info("🏌️  HOLE IN ONE MODE ACTIVE - Extended 4+ minute dung hole duration!")
    else:
        logger.info("🍋 NORMAL MODE - Standard 1:15 minute dung hole duration")
    
    logger.info("💡 Ready! Press '`' (backtick) to start automation...")
    logger.info("💡 Enhanced with human-like movement patterns to avoid detection!")
    logger.info("💡 Tip: Adjust anti-bot settings at top of script to customize behavior")
    logger.info("💡 Tip: Press 'c' to get current mouse coordinates for calibration")
    logger.info("💡 Tip: Coordinates are automatically scaled for your 250% DPI setting")
    logger.info("💡 Tip: Using pure Windows API - no pynput detection!")
    
    try:
        keyboard_monitor()
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()