# ANACRONIA AGILITY COURSE - SCRIPT 
#
# Instructions:
# - Camera: Freedom.
# - Camera Position: Zoomed Out + Top Maxed -> Facing West.

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

# Global state variables (must be at the very top)
running = False
current_step = 0
cycle_count = 0
click_thread = None
start_time = None
session_stats = {
    'total_cliff_face_clicks': 0,
    'total_ruined_temple_clicks': 0,
    'total_cave_entrance_clicks': 0,
    'total_cross_roots_clicks': 0,
    'total_moves': 0,
    'total_breaks': 0,
    'total_cycles': 0,
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

REGION_FILE = 'anacronia-agility-course.json'

# 12-Step Anacronia Agility Course Configuration
ANACRONIA_STEPS = [
    {
        'name': 'Traverse Cliff Face',
        'emoji': '🏔️',
        'duration': (3.75, 5.0),
        'region_key': 'CLIFF_FACE_REGION_1'
    },
    {
        'name': 'Traverse Cliff Face',
        'emoji': '🏔️',
        'duration': (5.5, 7.0),
        'region_key': 'CLIFF_FACE_REGION_2'
    },
    {
        'name': 'Traverse Ruined Temple',
        'emoji': '🏛️',
        'duration': (7.75, 9.0),
        'region_key': 'RUINED_TEMPLE_REGION_1'
    },
    {
        'name': 'Traverse Ruined Temple',
        'emoji': '🏛️',
        'duration': (8.0, 9.5),
        'region_key': 'RUINED_TEMPLE_REGION_2'
    },
    {
        'name': 'Enter Cave Entrance',
        'emoji': '🕳️',
        'duration': (7.0, 8.25),
        'region_key': 'CAVE_ENTRANCE_REGION_1'
    },
    {
        'name': 'Cross Roots',
        'emoji': '🌿',
        'duration': (8.25, 9.5),
        'region_key': 'CROSS_ROOTS_REGION_1'
    },
    {
        'name': 'Cross Roots',
        'emoji': '🌿',
        'duration': (8.25, 9.5),
        'region_key': 'CROSS_ROOTS_REGION_2'
    },
    {
        'name': 'Enter Cave Entrance',
        'emoji': '🕳️',
        'duration': (7.0, 8.25),
        'region_key': 'CAVE_ENTRANCE_REGION_2'
    },
    {
        'name': 'Traverse Ruined Temple',
        'emoji': '🏛️',
        'duration': (8.0, 9.5),
        'region_key': 'RUINED_TEMPLE_REGION_3'
    },
    {
        'name': 'Traverse Ruined Temple',
        'emoji': '🏛️',
        'duration': (7.75, 9.0),
        'region_key': 'RUINED_TEMPLE_REGION_4'
    },
    {
        'name': 'Traverse Cliff Face',
        'emoji': '🏔️',
        'duration': (5.5, 7.0),
        'region_key': 'CLIFF_FACE_REGION_3'
    },
    {
        'name': 'Traverse Cliff Face',
        'emoji': '🏔️',
        'duration': (6.0, 7.5),
        'region_key': 'CLIFF_FACE_REGION_4'
    }
]

# Use the single list for all operations
ALL_STEPS = ANACRONIA_STEPS

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
    print("\n--- Anacronia Agility Course Calibration Mode ---")
    regions = {}
    
    # Only calibrate steps that have regions
    for step in ALL_STEPS:
        if step['region_key']:
            regions[step['region_key']] = calibrate_region(step['name'])
    
    with open(REGION_FILE, 'w') as f:
        json.dump(regions, f)
    print(f"Regions saved to {REGION_FILE}!")
    return regions

def load_regions():
    if os.path.exists(REGION_FILE):
        with open(REGION_FILE, 'r') as f:
            return json.load(f)
    else:
        logger.warning("No region calibration found. Please calibrate (press 'c').")
        return calibrate_all_regions()

regions = load_regions()

MIN_CYCLES_BEFORE_BREAK = 6
BREAK_MIN_SEC     = 15
BREAK_MAX_SEC     = 35
INITIAL_DELAY_SEC = 10

PROGRESS_UPDATE_INTERVAL = 120
SHOW_DETAILED_PROGRESS = False
FORCE_GARBAGE_COLLECTION = True

ENABLE_CURVED_PATHS = True
ENABLE_OVERSHOOT = True
ENABLE_HESITATION = True
ENABLE_MICRO_CORRECTIONS = True
ENABLE_MOMENTUM = True
ENABLE_DISTRACTION_MOVES = True

CURVE_INTENSITY = 0.3
OVERSHOOT_CHANCE = 0.15
HESITATION_CHANCE = 0.25
DISTRACTION_CHANCE = 0.06
MICRO_CORRECTION_CHANCE = 0.4

# ─── Native Windows Mouse Click and Keyboard Input ───────────────────────────
PUL = ctypes.POINTER(ctypes.c_ulong)
class KeyBdInput(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", PUL)
    ]

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
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput)]

class Input(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("ii", Input_I)
    ]

# Constants for input types and flags
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP   = 0x0004
KEYEVENTF_KEYUP = 0x0002

def send_native_click(x=None, y=None):
    if x is not None and y is not None:
        windll.user32.SetCursorPos(int(x), int(y))
    extra = ctypes.c_ulong(0)
    ii_ = Input_I()
    ii_.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTDOWN, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
    windll.user32.SendInput(1, ctypes.pointer(command), ctypes.sizeof(command))
    time.sleep(0.01)
    ii_.mi = MouseInput(0, 0, 0, MOUSEEVENTF_LEFTUP, 0, ctypes.pointer(extra))
    command = Input(ctypes.c_ulong(INPUT_MOUSE), ii_)
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
        correction_steps = random.randint(3, 8)
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
    
    # Calculate region dimensions
    width = x_max - x_min
    height = y_max - y_min
    
    # For very small regions, use simple center-biased approach
    if width <= 5 or height <= 5:
        logger.debug(f"🎯 Small region detected ({width}x{height}), using center-biased approach")
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        
        # Add small random offset from center
        offset_x = random.uniform(-width/4, width/4)
        offset_y = random.uniform(-height/4, height/4)
        
        x = int(center_x + offset_x)
        y = int(center_y + offset_y)
        
        # Clamp to region bounds
        x = max(x_min, min(x_max, x))
        y = max(y_min, min(y_max, y))
        
        logger.debug(f"🎯 Small region target: ({x}, {y}) in region {region}")
        return x, y
    
    # Use different distribution strategies for better coverage on larger regions
    strategy = random.choice(['uniform', 'gaussian_center', 'gaussian_edge', 'corners'])
    
    if strategy == 'uniform':
        # Pure uniform distribution across entire region (most common)
        inset = max(1, min(3, min(width, height) // 20))  # Conservative inset for small regions
        
        # Ensure we don't get empty ranges
        x_min_safe = x_min + inset
        x_max_safe = x_max - inset
        y_min_safe = y_min + inset
        y_max_safe = y_max - inset
        
        # If inset makes range invalid, fall back to full region
        if x_min_safe >= x_max_safe:
            x_min_safe, x_max_safe = x_min, x_max
        if y_min_safe >= y_max_safe:
            y_min_safe, y_max_safe = y_min, y_max
            
        x = random.randint(x_min_safe, x_max_safe)
        y = random.randint(y_min_safe, y_max_safe)
        
    elif strategy == 'gaussian_center':
        # Gaussian distribution centered in the region
        center_x = (x_min + x_max) / 2
        center_y = (y_min + y_max) / 2
        
        # Use 1/4 of region size as standard deviation for good spread
        std_x = max(1, width / 4)  # Ensure std deviation is at least 1
        std_y = max(1, height / 4)
        
        x = int(random.gauss(center_x, std_x))
        y = int(random.gauss(center_y, std_y))
        
    elif strategy == 'gaussian_edge':
        # Bias toward edges of the region
        if random.random() < 0.5:
            # Bias toward left/right edges
            edge_x = x_min if random.random() < 0.5 else x_max
            x = int(random.gauss(edge_x, max(1, width / 8)))
            
            # Safe y range
            y_min_safe = y_min + 2
            y_max_safe = y_max - 2
            if y_min_safe >= y_max_safe:
                y_min_safe, y_max_safe = y_min, y_max
            y = random.randint(y_min_safe, y_max_safe)
        else:
            # Bias toward top/bottom edges
            edge_y = y_min if random.random() < 0.5 else y_max
            y = int(random.gauss(edge_y, max(1, height / 8)))
            
            # Safe x range
            x_min_safe = x_min + 2
            x_max_safe = x_max - 2
            if x_min_safe >= x_max_safe:
                x_min_safe, x_max_safe = x_min, x_max
            x = random.randint(x_min_safe, x_max_safe)
            
    else:  # corners
        # Bias toward corners for variety
        corner_bias = 0.3  # How close to corners
        if random.random() < 0.5:
            # Top corners
            if random.random() < 0.5:
                x = int(x_min + width * corner_bias * random.random())
                y = int(y_min + height * corner_bias * random.random())
            else:
                x = int(x_max - width * corner_bias * random.random())
                y = int(y_min + height * corner_bias * random.random())
        else:
            # Bottom corners
            if random.random() < 0.5:
                x = int(x_min + width * corner_bias * random.random())
                y = int(y_max - height * corner_bias * random.random())
            else:
                x = int(x_max - width * corner_bias * random.random())
                y = int(y_max - height * corner_bias * random.random())
    
    # Final bounds check - ensure coordinates stay within region
    x = max(x_min, min(x_max, x))
    y = max(y_min, min(y_max, y))
    
    logger.debug(f"🎯 Target strategy: {strategy}, coordinates: ({x}, {y}) in region {region}")
    
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

def print_stats():
    if session_stats['session_start']:
        elapsed = time.time() - session_stats['session_start']
        total_clicks = sum([
            session_stats['total_cliff_face_clicks'],
            session_stats['total_ruined_temple_clicks'],
            session_stats['total_cave_entrance_clicks'],
            session_stats['total_cross_roots_clicks']
        ])
        total_actions = total_clicks
        actions_per_min = (total_actions / elapsed) * 60 if elapsed > 0 else 0
        cycles_per_hour = (session_stats['total_cycles'] / elapsed) * 3600 if elapsed > 0 else 0
        
        logger.info("=" * 70)
        logger.info("🏃 ANACRONIA AGILITY COURSE SESSION STATISTICS")
        logger.info("=" * 70)
        logger.info("OBSTACLE ACTIONS:")
        logger.info(f"🏔️  Cliff Face Traversals: {session_stats['total_cliff_face_clicks']}")
        logger.info(f"🏛️  Ruined Temple Traversals: {session_stats['total_ruined_temple_clicks']}")
        logger.info(f"🕳️  Cave Entrance Entries: {session_stats['total_cave_entrance_clicks']}")
        logger.info(f"🌿 Root Crossings: {session_stats['total_cross_roots_clicks']}")
        logger.info("OVERALL:")
        logger.info(f"🔄 Total Cycles: {session_stats['total_cycles']}")
        logger.info(f"📍 Total Moves: {session_stats['total_moves']}")
        logger.info(f"☕ Total Breaks: {session_stats['total_breaks']}")
        logger.info(f"⏱️  Session Time: {format_time(elapsed)}")
        logger.info(f"⚡ Actions/Min: {actions_per_min:.1f}")
        logger.info(f"🔄 Cycles/Hour: {cycles_per_hour:.1f}")
        logger.info("=" * 70)

def execute_step(step_index):
    global session_stats
    
    step = ALL_STEPS[step_index]
    region_key = step['region_key']
    
    if region_key not in regions:
        logger.error(f"❌ Region not found for {step['name']}! Please calibrate.")
        return False
    
    region = tuple(regions[region_key])
    
    logger.info(f"{step['emoji']} Clicking {step['name']}...")
    tx, ty = random_target_within(region)
    logger.info(f"🎯 Moving to {step['name']}: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    current_x, current_y = get_current_mouse_position()
    set_mouse_position(current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    time.sleep(random.uniform(0.03, 0.12))
    
    send_native_click(*get_current_mouse_position())
    
    # Update specific obstacle stats
    if 'Cliff Face' in step['name']:
        session_stats['total_cliff_face_clicks'] += 1
        logger.info(f"✅ {step['name']} traversal #{session_stats['total_cliff_face_clicks']} completed at {get_current_mouse_position()}")
    elif 'Ruined Temple' in step['name']:
        session_stats['total_ruined_temple_clicks'] += 1
        logger.info(f"✅ {step['name']} traversal #{session_stats['total_ruined_temple_clicks']} completed at {get_current_mouse_position()}")
    elif 'Cave Entrance' in step['name']:
        session_stats['total_cave_entrance_clicks'] += 1
        logger.info(f"✅ {step['name']} entry #{session_stats['total_cave_entrance_clicks']} completed at {get_current_mouse_position()}")
    elif 'Cross Roots' in step['name']:
        session_stats['total_cross_roots_clicks'] += 1
        logger.info(f"✅ {step['name']} crossing #{session_stats['total_cross_roots_clicks']} completed at {get_current_mouse_position()}")
    else:
        logger.info(f"✅ {step['name']} completed at {get_current_mouse_position()}")
    
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

def anacronia_loop():
    global current_step, cycle_count, running, session_stats

    logger.info("🏃 Starting Anacronia Agility Course automation. Press '`' to stop, '~' to exit.")
    
    # Print all regions
    for step in ALL_STEPS:
        if step['region_key'] and step['region_key'] in regions:
            logger.info(f"{step['emoji']} {step['name']} Region: {regions[step['region_key']]}")
        elif step['region_key']:
            logger.warning(f"❌ {step['name']}: NOT CALIBRATED")
    
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC} seconds to switch screens...")
    for i in range(INITIAL_DELAY_SEC, 0, -1):
        if not running:
            logger.info("⏹️  Startup cancelled.")
            return
        logger.info(f"⏳ Starting in {i} seconds...")
        time.sleep(1)
    
    logger.info("🏃 Starting Anacronia Agility Course automation NOW!")
    
    current_step = 0
    
    while running:
        try:
            step = ALL_STEPS[current_step]
            
            logger.info(f"📍 Step {current_step + 1}/{len(ALL_STEPS)}")
            
            if not execute_step(current_step):
                break
            
            # Wait for step completion
            min_duration, max_duration = step['duration']
            wait_time = random.uniform(min_duration, max_duration)
            
            # Determine next step description
            next_step_index = current_step + 1
            if next_step_index >= len(ALL_STEPS):
                next_step_name = "cycle completion"
            else:
                next_step_name = ALL_STEPS[next_step_index]['name']
            
            smart_wait(wait_time, f"completing {step['name']} -> {next_step_name}")
            
            # Move to next step
            current_step = (current_step + 1) % len(ALL_STEPS)
            
            # Check if we completed a full cycle
            if current_step == 0:
                cycle_count += 1
                session_stats['total_cycles'] += 1
                logger.info(f"🔄 ======================================== Cycle #{cycle_count} completed!")
                
                # Print stats every 2 cycles
                if cycle_count % 2 == 0:
                    print_stats()
                    if FORCE_GARBAGE_COLLECTION:
                        gc.collect()
                
                # Take break every few cycles
                if cycle_count % MIN_CYCLES_BEFORE_BREAK == 0:
                    break_duration = random.uniform(BREAK_MIN_SEC, BREAK_MAX_SEC)
                    session_stats['total_breaks'] += 1
                    logger.info(f"☕ Taking break #{session_stats['total_breaks']} for {break_duration:.1f}s after {cycle_count} cycles...")
                    
                    smart_wait(break_duration, "break completion")
                    
                    if running:
                        logger.info("🔄 Break finished, resuming Anacronia Agility Course automation...")
                        
        except Exception as e:
            logger.error(f"❌ Error in Anacronia agility loop: {e}")
            break
    
    logger.info("⏸️  Anacronia agility loop stopped.")

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
        click_thread = threading.Thread(target=anacronia_loop, daemon=True)
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
    global regions
    logger.info("🎯 CALIBRATION MODE - Recalibrating all regions")
    regions = calibrate_all_regions()
    logger.info("✅ Calibration complete! New regions saved.")

def main():
    logger.info("🏃 Enhanced Anti-Bot Anacronia Agility Course Automation")
    logger.info("=" * 70)
    logger.info(f"⌨️  START/STOP: Press '`' (backtick)")
    logger.info(f"⌨️  EXIT: Press '~' (tilde)")
    logger.info(f"🎯 CALIBRATION: Press 'c' to recalibrate all regions")
    logger.info("─" * 70)
    logger.info("🏃 ANACRONIA AGILITY COURSE CONFIGURATION:")
    
    logger.info("\n🔄 12-STEP SEQUENCE:")
    for i, step in enumerate(ALL_STEPS, 1):
        region_key = step['region_key']
        duration = step['duration']
        if region_key and region_key in regions:
            logger.info(f"{step['emoji']} {i}. {step['name']}: {regions[region_key]} ({duration[0]:.2f}-{duration[1]:.2f}s)")
        elif region_key:
            logger.warning(f"❌ {i}. {step['name']}: NOT CALIBRATED ({duration[0]:.2f}-{duration[1]:.2f}s)")
        else:
            logger.info(f"{step['emoji']} {i}. {step['name']}: ({duration[0]:.2f}-{duration[1]:.2f}s)")
    
    logger.info("─" * 70)
    logger.info("🤖 ANTI-BOT DETECTION FEATURES:")
    logger.info(f"🏹 Curved Paths: {'✅ Enabled' if ENABLE_CURVED_PATHS else '❌ Disabled'}")
    logger.info(f"🎯 Overshoot Correction: {'✅ Enabled' if ENABLE_OVERSHOOT else '❌ Disabled'} ({OVERSHOOT_CHANCE*100:.0f}% chance)")
    logger.info(f"⏸️ Hesitation Pauses: {'✅ Enabled' if ENABLE_HESITATION else '❌ Disabled'} ({HESITATION_CHANCE*100:.0f}% chance)")
    logger.info(f"🔧 Micro Corrections: {'✅ Enabled' if ENABLE_MICRO_CORRECTIONS else '❌ Disabled'} ({MICRO_CORRECTION_CHANCE*100:.0f}% chance)")
    logger.info(f"🌊 Momentum Simulation: {'✅ Enabled' if ENABLE_MOMENTUM else '❌ Disabled'}")
    logger.info(f"👀 Distraction Moves: {'✅ Enabled' if ENABLE_DISTRACTION_MOVES else '❌ Disabled'} ({DISTRACTION_CHANCE*100:.0f}% chance)")
    logger.info(f"🎨 Curve Intensity: {CURVE_INTENSITY*100:.0f}%")
    logger.info("─" * 70)
    logger.info(f"☕ Break Every: {MIN_CYCLES_BEFORE_BREAK} cycles")
    logger.info(f"⏳ Initial Delay: {INITIAL_DELAY_SEC} seconds")
    logger.info(f"📊 Progress Updates: Every {PROGRESS_UPDATE_INTERVAL}s for long waits")
    logger.info("=" * 70)
    logger.info("🏃 ANACRONIA AGILITY COURSE SEQUENCE:")
    
    for i, step in enumerate(ALL_STEPS, 1):
        duration = step['duration']
        logger.info(f"{step['emoji']} {i}. {step['name']} ({duration[0]:.2f}-{duration[1]:.2f}s)")
        if i < len(ALL_STEPS):
            logger.info("   ⬇️")
        else:
            logger.info("   🔄 Loop back to step 1")
    
    logger.info("=" * 70)
    
    # Check if all regions are calibrated
    missing_regions = []
    for step in ALL_STEPS:
        if step['region_key'] and step['region_key'] not in regions:
            missing_regions.append(step['name'])
    
    if missing_regions:
        logger.warning(f"❌ Missing calibration for: {', '.join(missing_regions)}")
        logger.warning("⚠️  Please press 'c' to calibrate all regions before starting!")
    else:
        logger.info("✅ All regions calibrated and ready!")
    
    logger.info("💡 Ready! Press '`' (backtick) to start automation...")
    logger.info("💡 Enhanced with human-like movement patterns to avoid detection!")
    logger.info("💡 Tip: Adjust anti-bot settings at top of script to customize behavior")
    logger.info("💡 Tip: Press 'c' to recalibrate all obstacle regions")
    logger.info("💡 Tip: Using pure Windows API - no pynput detection!")
    logger.info("💡 12-Step Course: Cliff Face (x2) → Ruined Temple (x2) → Cave → Roots (x2) → Cave → Ruined Temple (x2) → Cliff Face (x2)")
    
    try:
        keyboard_monitor()
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()