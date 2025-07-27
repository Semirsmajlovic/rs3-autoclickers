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
current_obstacle = 0
lap_count = 0
click_thread = None
start_time = None
session_stats = {
    'total_rope_swing_clicks': 0,
    'total_log_balance_clicks': 0,
    'total_run_up_wall_clicks': 0,
    'total_climb_up_wall_clicks': 0,
    'total_fire_spring_device_clicks': 0,
    'total_cross_balance_beam_clicks': 0,
    'total_jump_over_gap_clicks': 0,
    'total_slide_down_roof_clicks': 0,
    'total_walk_to_start_clicks': 0,
    'total_moves': 0,
    'total_breaks': 0,
    'total_laps': 0,
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

REGION_FILE = 'barbarian-agility-course-regions.json'

# Agility Course Obstacles Configuration
OBSTACLES = [
    {
        'name': 'Rope Swing',
        'emoji': '🪢',
        'duration': (3.5, 5.0),
        'region_key': 'ROPE_SWING_REGION'
    },
    {
        'name': 'Log Balance',
        'emoji': '🪵',
        'duration': (10.0, 12.0),
        'region_key': 'LOG_BALANCE_REGION'
    },
    {
        'name': 'Run-up Wall',
        'emoji': '🏃',
        'duration': (10.0, 12.0),
        'region_key': 'RUN_UP_WALL_REGION'
    },
    {
        'name': 'Climb-up Wall',
        'emoji': '🧗',
        'duration': (6.0, 8.0),
        'region_key': 'CLIMB_UP_WALL_REGION'
    },
    {
        'name': 'Fire Spring Device',
        'emoji': '🔥',
        'duration': (8.0, 10.0),
        'region_key': 'FIRE_SPRING_DEVICE_REGION'
    },
    {
        'name': 'Cross Balance Beam',
        'emoji': '⚖️',
        'duration': (5.0, 7.0),
        'region_key': 'CROSS_BALANCE_BEAM_REGION'
    },
    {
        'name': 'Jump over Gap',
        'emoji': '🦘',
        'duration': (3.0, 5.0),
        'region_key': 'JUMP_OVER_GAP_REGION'
    },
    {
        'name': 'Slide-down Roof',
        'emoji': '🛝',
        'duration': (5.0, 7.0),
        'region_key': 'SLIDE_DOWN_ROOF_REGION'
    },
    {
        'name': 'Walk to Start',
        'emoji': '🚶',
        'duration': (4.0, 6.0),
        'region_key': 'WALK_TO_START_REGION'
    }
]

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
    
    # Ensure coordinates are in correct order
    x_min, x_max = min(x1, x2), max(x1, x2)
    y_min, y_max = min(y1, y2), max(y1, y2)
    
    # Ensure minimum region size (very conservative expansion)
    if x_max - x_min < 4:
        print(f"⚠️  Region too narrow ({x_max - x_min}px), expanding by 2px")
        center_x = (x_min + x_max) / 2
        x_min = int(center_x - 2)
        x_max = int(center_x + 2)
    
    if y_max - y_min < 4:
        print(f"⚠️  Region too short ({y_max - y_min}px), expanding by 2px")
        center_y = (y_min + y_max) / 2
        y_min = int(center_y - 2)
        y_max = int(center_y + 2)
    
    region = (x_min, y_min, x_max, y_max)
    print(f"{name} region: {region} (width: {x_max-x_min}px, height: {y_max-y_min}px)")
    return region

def calibrate_all_regions():
    print("\n--- Barbarian Agility Course Calibration Mode ---")
    regions = {}
    
    for obstacle in OBSTACLES:
        regions[obstacle['region_key']] = calibrate_region(obstacle['name'])
    
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

MIN_LAPS_BEFORE_BREAK = 5
BREAK_MIN_SEC     = 8
BREAK_MAX_SEC     = 20
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
    
    # Ensure coordinates are in correct order (swap if needed)
    if x_min > x_max:
        x_min, x_max = x_max, x_min
        logger.warning(f"⚠️  Swapped X coordinates: min={x_min}, max={x_max}")
    if y_min > y_max:
        y_min, y_max = y_max, y_min
        logger.warning(f"⚠️  Swapped Y coordinates: min={y_min}, max={y_max}")
    
    # Ensure minimum region size (very conservative expansion)
    if x_max - x_min < 4:
        logger.warning(f"⚠️  Region too narrow ({x_max - x_min}px), expanding by 2px...")
        center_x = (x_min + x_max) / 2
        x_min = int(center_x - 2)
        x_max = int(center_x + 2)
    
    if y_max - y_min < 4:
        logger.warning(f"⚠️  Region too short ({y_max - y_min}px), expanding by 2px...")
        center_y = (y_min + y_max) / 2
        y_min = int(center_y - 2)
        y_max = int(center_y + 2)
    
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    
    if random.random() < 0.7:
        # Target near center with small offset
        offset_x = random.uniform(-2, 2)  # Reduced from -8, 8
        offset_y = random.uniform(-2, 2)  # Reduced from -8, 8
        x = int(center_x + offset_x)
        y = int(center_y + offset_y)
    else:
        # Target anywhere in region with minimal inset
        inset = 1  # Reduced from 4
        try:
            x = random.randint(x_min + inset, x_max - inset)
            y = random.randint(y_min + inset, y_max - inset)
        except ValueError as e:
            logger.warning(f"⚠️  Random range error: {e}. Using center coordinates.")
            x = int(center_x)
            y = int(center_y)
    
    # Final bounds check with minimal padding
    x = max(x_min + 1, min(x_max - 1, x))  # Reduced from +2, -2
    y = max(y_min + 1, min(y_max - 1, y))  # Reduced from +2, -2
    
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
            session_stats['total_rope_swing_clicks'],
            session_stats['total_log_balance_clicks'],
            session_stats['total_run_up_wall_clicks'],
            session_stats['total_climb_up_wall_clicks'],
            session_stats['total_fire_spring_device_clicks'],
            session_stats['total_cross_balance_beam_clicks'],
            session_stats['total_jump_over_gap_clicks'],
            session_stats['total_slide_down_roof_clicks'],
            session_stats['total_walk_to_start_clicks']
        ])
        clicks_per_min = (total_clicks / elapsed) * 60 if elapsed > 0 else 0
        laps_per_hour = (session_stats['total_laps'] / elapsed) * 3600 if elapsed > 0 else 0
        
        logger.info("=" * 70)
        logger.info("🏃 BARBARIAN AGILITY COURSE SESSION STATISTICS")
        logger.info("=" * 70)
        logger.info(f"🪢 Rope Swing: {session_stats['total_rope_swing_clicks']}")
        logger.info(f"🪵 Log Balance: {session_stats['total_log_balance_clicks']}")
        logger.info(f"🏃 Run-up Wall: {session_stats['total_run_up_wall_clicks']}")
        logger.info(f"🧗 Climb-up Wall: {session_stats['total_climb_up_wall_clicks']}")
        logger.info(f"🔥 Fire Spring Device: {session_stats['total_fire_spring_device_clicks']}")
        logger.info(f"⚖️ Cross Balance Beam: {session_stats['total_cross_balance_beam_clicks']}")
        logger.info(f"🦘 Jump over Gap: {session_stats['total_jump_over_gap_clicks']}")
        logger.info(f"🛝 Slide-down Roof: {session_stats['total_slide_down_roof_clicks']}")
        logger.info(f"🚶 Walk to Start: {session_stats['total_walk_to_start_clicks']}")
        logger.info(f"🏁 Total Laps: {session_stats['total_laps']}")
        logger.info(f"📍 Total Moves: {session_stats['total_moves']}")
        logger.info(f"☕ Total Breaks: {session_stats['total_breaks']}")
        logger.info(f"⏱️  Session Time: {format_time(elapsed)}")
        logger.info(f"⚡ Clicks/Min: {clicks_per_min:.1f}")
        logger.info(f"🏃 Laps/Hour: {laps_per_hour:.1f}")
        logger.info("=" * 70)

def click_obstacle(obstacle_index):
    global session_stats
    
    obstacle = OBSTACLES[obstacle_index]
    region_key = obstacle['region_key']
    
    if region_key not in regions:
        logger.error(f"❌ Region not found for {obstacle['name']}! Please calibrate.")
        return False
    
    region = tuple(regions[region_key])
    
    logger.info(f"{obstacle['emoji']} Clicking {obstacle['name']}...")
    
    try:
        tx, ty = random_target_within(region)
        logger.info(f"🎯 Moving to {obstacle['name']}: ({tx}, {ty})")
        human_move(tx, ty)
        
        if not running:
            return False
        
        current_x, current_y = get_current_mouse_position()
        set_mouse_position(current_x + random.uniform(-0.8, 0.8), 
                         current_y + random.uniform(-0.8, 0.8))
        
        time.sleep(random.uniform(0.03, 0.12))
        
        send_native_click(*get_current_mouse_position())
        
        # Update stats
        stats_key = f"total_{obstacle['name'].lower().replace('-', '_').replace(' ', '_')}_clicks"
        session_stats[stats_key] += 1
        
        logger.info(f"✅ {obstacle['name']} click #{session_stats[stats_key]} completed at {get_current_mouse_position()}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error clicking {obstacle['name']}: {e}")
        logger.error(f"❌ Region was: {region}")
        return False

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

def agility_course_loop():
    global current_obstacle, lap_count, running, session_stats

    logger.info("🏃 Starting Barbarian Agility Course automation. Press '`' to stop, '~' to exit.")
    
    # Print all regions
    for obstacle in OBSTACLES:
        region_key = obstacle['region_key']
        if region_key in regions:
            logger.info(f"{obstacle['emoji']} {obstacle['name']} Region: {regions[region_key]}")
    
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC} seconds to switch screens...")
    for i in range(INITIAL_DELAY_SEC, 0, -1):
        if not running:
            logger.info("⏹️  Startup cancelled.")
            return
        logger.info(f"⏳ Starting in {i} seconds...")
        time.sleep(1)
    
    logger.info("🏃 Starting agility course NOW!")
    
    current_obstacle = 0
    
    while running:
        try:
            # Click current obstacle
            obstacle = OBSTACLES[current_obstacle]
            
            if not click_obstacle(current_obstacle):
                break
            
            # Wait for obstacle completion
            min_duration, max_duration = obstacle['duration']
            wait_time = random.uniform(min_duration, max_duration)
            
            next_obstacle_name = OBSTACLES[(current_obstacle + 1) % len(OBSTACLES)]['name']
            smart_wait(wait_time, f"completing {obstacle['name']} -> {next_obstacle_name}")
            
            # Move to next obstacle
            current_obstacle = (current_obstacle + 1) % len(OBSTACLES)
            
            # Check if we completed a full lap
            if current_obstacle == 0:
                lap_count += 1
                session_stats['total_laps'] += 1
                logger.info(f"🏁 Lap #{lap_count} completed!")
                
                # Print stats every 5 laps
                if lap_count % 5 == 0:
                    print_stats()
                    if FORCE_GARBAGE_COLLECTION:
                        gc.collect()
                
                # Take break every few laps
                if lap_count % MIN_LAPS_BEFORE_BREAK == 0:
                    break_duration = random.uniform(BREAK_MIN_SEC, BREAK_MAX_SEC)
                    session_stats['total_breaks'] += 1
                    logger.info(f"☕ Taking break #{session_stats['total_breaks']} for {break_duration:.1f}s after {lap_count} laps...")
                    
                    smart_wait(break_duration, "break completion")
                    
                    if running:
                        logger.info("🔄 Break finished, resuming agility course...")
                        
        except Exception as e:
            logger.error(f"❌ Error in agility course loop: {e}")
            break
    
    logger.info("⏸️  Agility course loop stopped.")

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
        click_thread = threading.Thread(target=agility_course_loop, daemon=True)
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
    logger.info("🏃 Enhanced Anti-Bot Barbarian Agility Course Automation")
    logger.info("=" * 70)
    logger.info(f"⌨️  START/STOP: Press '`' (backtick)")
    logger.info(f"⌨️  EXIT: Press '~' (tilde)")
    logger.info(f"🎯 CALIBRATION: Press 'c' to recalibrate all regions")
    logger.info("─" * 70)
    logger.info("🖥️  AGILITY COURSE CONFIGURATION:")
    
    for i, obstacle in enumerate(OBSTACLES, 1):
        region_key = obstacle['region_key']
        if region_key in regions:
            duration = obstacle['duration']
            logger.info(f"{obstacle['emoji']} {i}. {obstacle['name']}: {regions[region_key]} ({duration[0]:.1f}-{duration[1]:.1f}s)")
        else:
            logger.warning(f"❌ {i}. {obstacle['name']}: NOT CALIBRATED")
    
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
    logger.info(f"☕ Break Every: {MIN_LAPS_BEFORE_BREAK} laps")
    logger.info(f"⏳ Initial Delay: {INITIAL_DELAY_SEC} seconds")
    logger.info(f"📊 Progress Updates: Every {PROGRESS_UPDATE_INTERVAL}s for long waits")
    logger.info("=" * 70)
    logger.info("🏃 AGILITY COURSE SEQUENCE:")
    
    for i, obstacle in enumerate(OBSTACLES, 1):
        duration = obstacle['duration']
        logger.info(f"{obstacle['emoji']} {i}. {obstacle['name']} ({duration[0]:.1f}-{duration[1]:.1f}s)")
        if i < len(OBSTACLES):
            logger.info("   ⬇️")
    
    logger.info("   🔄 Loop back to start")
    logger.info("=" * 70)
    
    # Check if all regions are calibrated
    missing_regions = []
    for obstacle in OBSTACLES:
        if obstacle['region_key'] not in regions:
            missing_regions.append(obstacle['name'])
    
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
    
    try:
        keyboard_monitor()
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()