import time
import random
import logging
import sys
import threading
import math
import gc  # For garbage collection
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Listener, KeyCode

# ─── Platform Configuration ──────────────────────────────────────────────────
LAPTOP_PLATFORM = "Windows"  # Set to "Mac" or "Windows"

# ─── Configuration ────────────────────────────────────────────────────────────
START_STOP_KEY    = KeyCode(char='`')  # Backtick/grave accent key
EXIT_KEY          = KeyCode(char='~')  # Tilde key

# Platform-specific coordinates
if LAPTOP_PLATFORM == "Windows":
    DUNG_HOLE_REGION  = (1870, 870, 1995, 983)   # Windows coordinates
    LEMON_SOUR_REGION = (3727, 1492, 3782, 1554) # Windows Lemon Sour coordinates
    HOLE_IN_ONE_REGION = (3727, 1406, 3782, 1462) # Windows Hole in One coordinates
else:  # Mac (default)
    DUNG_HOLE_REGION  = (830, 605, 895, 670)     # Mac coordinates
    LEMON_SOUR_REGION = (1680, 875, 1705, 900)   # Mac Lemon Sour coordinates
    HOLE_IN_ONE_REGION = (1680, 840, 1705, 865)  # Mac Hole in One coordinates

MIN_CLICKS_BEFORE_BREAK = 20
BREAK_MIN_SEC     = 5
BREAK_MAX_SEC     = 15
INITIAL_DELAY_SEC = 10  # Delay before first click starts

# ─── Logging Configuration ────────────────────────────────────────────────────
PROGRESS_UPDATE_INTERVAL = 120  # Show progress every 2 minutes instead of 1
SHOW_DETAILED_PROGRESS = False  # Set to True to see more frequent updates
FORCE_GARBAGE_COLLECTION = True  # Force garbage collection periodically

# ─── Hole in One Configuration ────────────────────────────────────────────────
USE_HOLE_IN_ONE = False  # Set to True to enable Hole in One cocktail, False to disable
COCKTAIL_INTERVAL_NORMAL = 10  # Click cocktails every X dung hole cycles (without Hole in One)
COCKTAIL_INTERVAL_HOLE_IN_ONE = 4  # Click cocktails every X dung hole cycles (with Hole in One)
DUNG_HOLE_DURATION_NORMAL = (79, 90)  # Wait time without Hole in One (77-90 seconds)
DUNG_HOLE_DURATION_HOLE_IN_ONE = (242, 250)  # Wait time with Hole in One (4:02-4:10 minutes)

# ─── Enhanced Anti-Bot Detection Settings ──────────────────────────────────────
# Movement behavior settings
ENABLE_CURVED_PATHS = True      # Enable curved/arc movements instead of straight lines
ENABLE_OVERSHOOT = True         # Sometimes overshoot target and correct back
ENABLE_HESITATION = True        # Add hesitation pauses during movement
ENABLE_MICRO_CORRECTIONS = True # Add small corrections after reaching target
ENABLE_MOMENTUM = True          # Simulate mouse momentum/inertia
ENABLE_DISTRACTION_MOVES = True # Occasionally move to random spots first

# Movement parameters
CURVE_INTENSITY = 0.3           # How curved the paths are (0.0-1.0)
OVERSHOOT_CHANCE = 0.15         # Chance to overshoot target (0.0-1.0)
HESITATION_CHANCE = 0.25        # Chance to pause during movement (0.0-1.0)
DISTRACTION_CHANCE = 0.08       # Chance to move to random spot first (0.0-1.0)
MICRO_CORRECTION_CHANCE = 0.4   # Chance to do small corrections after reaching target

# Enhanced logging with colors
class ColoredFormatter(logging.Formatter):
    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m'  # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        return super().format(record)

# Setup logging with memory optimization
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
# Force immediate flush to prevent buffer accumulation
handler.flush = lambda: handler.stream.flush()
logger.addHandler(handler)

mouse = MouseController()
running = False
click_count = 0
click_thread = None
start_time = None
session_stats = {
    'total_dung_clicks': 0,
    'total_lemon_clicks': 0,
    'total_hole_in_one_clicks': 0,
    'total_moves': 0,
    'total_breaks': 0,
    'session_start': None,
    'cocktail_cycles': 0
}

# ─── Add this function after the existing helper functions ───────────────────
def get_platform_info():
    """Get current platform configuration info."""
    return {
        'platform': LAPTOP_PLATFORM,
        'dung_hole': DUNG_HOLE_REGION,
        'lemon_sour': LEMON_SOUR_REGION,
        'hole_in_one': HOLE_IN_ONE_REGION
    }

# ─── Enhanced Human-like Movement System ───────────────────────────────────────

def bezier_curve(t, p0, p1, p2, p3):
    """Calculate point on cubic Bézier curve at parameter t (0-1)"""
    return ((1-t)**3 * p0 + 3*(1-t)**2*t * p1 + 3*(1-t)*t**2 * p2 + t**3 * p3)

def ease_in_out_cubic(t):
    """Smooth cubic easing function"""
    return 4*t*t*t if t < 0.5 else 1-pow(-2*t+2, 3)/2

def ease_out_quad(t: float) -> float:
    """Quadratic ease-out: fast start, slow end."""
    return 1 - (1 - t) * (1 - t)

def generate_curve_points(start_x, start_y, end_x, end_y, curve_intensity=0.3):
    """Generate control points for a curved path using Bézier curves"""
    mid_x = (start_x + end_x) / 2
    mid_y = (start_y + end_y) / 2
    
    # Calculate perpendicular offset for curve
    dx = end_x - start_x
    dy = end_y - start_y
    distance = math.sqrt(dx*dx + dy*dy)
    
    if distance < 10:  # Too close for curves
        return None
    
    # Create perpendicular vector
    perp_x = -dy / distance
    perp_y = dx / distance
    
    # Random curve direction and intensity
    curve_offset = random.uniform(-distance * curve_intensity, distance * curve_intensity)
    
    # Control points for Bézier curve
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
    """Sometimes move to a random nearby location first (simulating distraction)"""
    if not ENABLE_DISTRACTION_MOVES or random.random() > DISTRACTION_CHANCE:
        return
    
    current_x, current_y = mouse.position
    
    # Generate random distraction point within reasonable range
    distraction_x = current_x + random.randint(-200, 200)
    distraction_y = current_y + random.randint(-100, 100)
    
    # Keep within reasonable screen bounds (assuming 1920x1080+)
    distraction_x = max(100, min(1800, distraction_x))
    distraction_y = max(100, min(1000, distraction_y))
    
    logger.debug(f"🎯 Distraction movement to ({distraction_x}, {distraction_y})")
    
    # Quick movement to distraction point
    simple_move_to(distraction_x, distraction_y, speed_multiplier=1.5)
    
    # Brief pause at distraction point
    time.sleep(random.uniform(0.1, 0.4))

def simple_move_to(to_x, to_y, speed_multiplier=1.0):
    """Simple movement without curves for distraction moves"""
    start_x, start_y = mouse.position
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
        
        # Light jitter
        jitter = (1 - t) * 0.3
        cur_x += random.uniform(-jitter, jitter)
        cur_y += random.uniform(-jitter, jitter)
        
        mouse.position = (cur_x, cur_y)
        time.sleep(random.uniform(0.005, 0.012) / speed_multiplier)

def human_move(to_x: int, to_y: int):
    """
    Enhanced human-like movement with curves, overshooting, hesitation, and more
    """
    global session_stats
    start_x, start_y = mouse.position
    distance = math.sqrt((to_x - start_x)**2 + (to_y - start_y)**2)

    if distance < 3:  # Already close enough
        return
    
    # Occasionally add distraction movement first
    add_distraction_movement()
    
    # Recalculate after potential distraction
    start_x, start_y = mouse.position
    distance = math.sqrt((to_x - start_x)**2 + (to_y - start_y)**2)
    
    logger.debug(f"🎯 Enhanced move from ({start_x:.0f}, {start_y:.0f}) to ({to_x}, {to_y}) - Distance: {distance:.1f}px")
    
    # Determine movement strategy
    use_curves = ENABLE_CURVED_PATHS and distance > 50 and random.random() < 0.7
    will_overshoot = ENABLE_OVERSHOOT and distance > 30 and random.random() < OVERSHOOT_CHANCE
    
    # Calculate target (potentially with overshoot)
    target_x, target_y = to_x, to_y
    if will_overshoot:
        overshoot_distance = random.uniform(5, 15)
        angle = math.atan2(to_y - start_y, to_x - start_x)
        target_x = to_x + overshoot_distance * math.cos(angle)
        target_y = to_y + overshoot_distance * math.sin(angle)
        logger.debug(f"🎯 Overshoot target: ({target_x:.0f}, {target_y:.0f})")
    
    # Generate movement path
    steps = int(max(10, min(40, distance / 2)))
    
    if use_curves:
        # Use Bézier curve for natural arc movement
        curve_points = generate_curve_points(start_x, start_y, target_x, target_y, CURVE_INTENSITY)
        if curve_points:
            logger.debug("🏹 Using curved path")
            move_along_curve(curve_points, steps, distance)
        else:
            move_straight_enhanced(start_x, start_y, target_x, target_y, steps)
    else:
        move_straight_enhanced(start_x, start_y, target_x, target_y, steps)
    
    # Correct overshoot if needed
    if will_overshoot and running:
        logger.debug("🎯 Correcting overshoot...")
        time.sleep(random.uniform(0.05, 0.15))  # Brief realization pause
        correction_steps = random.randint(3, 8)
        move_straight_enhanced(mouse.position[0], mouse.position[1], to_x, to_y, correction_steps)
    
    # Micro-corrections for final positioning
    if ENABLE_MICRO_CORRECTIONS and random.random() < MICRO_CORRECTION_CHANCE and running:
        time.sleep(random.uniform(0.02, 0.08))
        final_x = to_x + random.uniform(-1, 1)
        final_y = to_y + random.uniform(-1, 1)
        mouse.position = (final_x, final_y)
        logger.debug(f"🔧 Micro-correction to ({final_x:.0f}, {final_y:.0f})")
    
    session_stats['total_moves'] += 1
    
    # Final positioning pause
    time.sleep(random.uniform(0.08, 0.2))

def move_along_curve(curve_points, steps, distance):
    """Move mouse along a Bézier curve"""
    p0, p1, p2, p3 = curve_points['p0'], curve_points['p1'], curve_points['p2'], curve_points['p3']
    
    for i in range(steps):
        if not running:
            break
        
        t = (i + 1) / steps
        
        # Use different easing for different parts of the movement
        if t < 0.3:
            t_eased = ease_in_out_cubic(t / 0.3) * 0.3
        elif t > 0.7:
            t_eased = 0.7 + ease_in_out_cubic((t - 0.7) / 0.3) * 0.3
        else:
            t_eased = t
        
        # Calculate position on curve
        cur_x = bezier_curve(t_eased, p0[0], p1[0], p2[0], p3[0])
        cur_y = bezier_curve(t_eased, p0[1], p1[1], p2[1], p3[1])
        
        # Add dynamic jitter (more at start, less at end)
        jitter_strength = (1 - t) * 0.8
        cur_x += random.uniform(-jitter_strength, jitter_strength)
        cur_y += random.uniform(-jitter_strength, jitter_strength)
        
        mouse.position = (cur_x, cur_y)
        
        # Variable speed with occasional hesitation
        base_sleep = random.uniform(0.008, 0.018)
        
        # Add hesitation pauses
        if ENABLE_HESITATION and random.random() < HESITATION_CHANCE * (1 - t):
            hesitation_time = random.uniform(0.02, 0.08)
            logger.debug(f"⏸️ Hesitation pause: {hesitation_time:.3f}s")
            time.sleep(hesitation_time)
        
        # Momentum simulation - faster in middle of movement
        if ENABLE_MOMENTUM:
            momentum_factor = 1 - abs(t - 0.5) * 0.4  # Faster in middle
            base_sleep *= momentum_factor
        
        time.sleep(base_sleep)

def move_straight_enhanced(start_x, start_y, target_x, target_y, steps):
    """Enhanced straight-line movement with human-like characteristics"""
    for i in range(steps):
        if not running:
            break
        
        t = (i + 1) / steps
        t_eased = ease_in_out_cubic(t)
        
        cur_x = start_x + (target_x - start_x) * t_eased
        cur_y = start_y + (target_y - start_y) * t_eased
        
        # Enhanced jitter with noise
        jitter_strength = (1 - t) * 0.7
        noise_x = random.uniform(-jitter_strength, jitter_strength)
        noise_y = random.uniform(-jitter_strength, jitter_strength)
        
        # Add slight tremor effect
        tremor_x = math.sin(t * 20) * 0.1 * jitter_strength
        tremor_y = math.cos(t * 25) * 0.1 * jitter_strength
        
        cur_x += noise_x + tremor_x
        cur_y += noise_y + tremor_y
        
        mouse.position = (cur_x, cur_y)
        
        # Variable timing with hesitation
        base_sleep = random.uniform(0.006, 0.016)
        
        if ENABLE_HESITATION and random.random() < HESITATION_CHANCE * (1 - t):
            hesitation_time = random.uniform(0.015, 0.06)
            time.sleep(hesitation_time)
        
        time.sleep(base_sleep)

def random_target_within(region):
    """Return a random (x,y) inside the given region with intelligent targeting"""
    x_min, y_min, x_max, y_max = region
    
    # Create weighted random targeting (avoid perfect center every time)
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    
    # 70% chance to target center area, 30% chance for edges
    if random.random() < 0.7:
        # Target center area with slight offset
        offset_x = random.uniform(-8, 8)
        offset_y = random.uniform(-8, 8)
        x = int(center_x + offset_x)
        y = int(center_y + offset_y)
    else:
        # Target edges/corners occasionally
        inset = 4
        x = random.randint(x_min + inset, x_max - inset)
        y = random.randint(y_min + inset, y_max - inset)
    
    # Ensure within bounds
    x = max(x_min + 2, min(x_max - 2, x))
    y = max(y_min + 2, min(y_max - 2, y))
    
    return x, y

def format_time(seconds):
    """Format seconds into human-readable time."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def get_current_settings():
    """Get current configuration settings based on Hole in One mode."""
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
    """Print current session statistics."""
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
    """Click on the Hole in One cocktail."""
    global session_stats
    
    logger.info("🏌️  Clicking Hole in One cocktail...")
    tx, ty = random_target_within(HOLE_IN_ONE_REGION)
    logger.info(f"🎯 Moving to Hole in One: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    # Pre-click micro-adjustment
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    # Brief pre-click pause (like human aiming)
    time.sleep(random.uniform(0.03, 0.12))
    
    # Perform click
    mouse.click(Button.left, 1)
    session_stats['total_hole_in_one_clicks'] += 1
    
    logger.info(f"✅ Hole in One click #{session_stats['total_hole_in_one_clicks']} completed at ({mouse.position[0]:.0f}, {mouse.position[1]:.0f})")
    return True

def click_lemon_sour():
    """Click on the Lemon Sour cocktail."""
    global session_stats
    
    logger.info("🍋 Clicking Lemon Sour cocktail...")
    tx, ty = random_target_within(LEMON_SOUR_REGION)
    logger.info(f"🎯 Moving to Lemon Sour: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    # Pre-click micro-adjustment
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    # Brief pre-click pause
    time.sleep(random.uniform(0.03, 0.12))
    
    # Perform click
    mouse.click(Button.left, 1)
    session_stats['total_lemon_clicks'] += 1
    
    logger.info(f"✅ Lemon Sour click #{session_stats['total_lemon_clicks']} completed at ({mouse.position[0]:.0f}, {mouse.position[1]:.0f})")
    return True

def click_cocktails():
    """Click cocktails based on current mode."""
    logger.info("🍹 Starting cocktail sequence...")
    
    if USE_HOLE_IN_ONE:
        # Hole in One mode: click Hole in One first, then Lemon Sour
        if not click_hole_in_one():
            return False
            
        # Wait between cocktails with human-like variability
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
        # Normal mode: just click Lemon Sour
        if not click_lemon_sour():
            return False
    
    logger.info("🍹 Cocktail sequence completed!")
    return True

def click_dung_hole():
    """Click on the dung hole."""
    global click_count, session_stats
    
    logger.info("🕳️  Clicking dung hole...")
    tx, ty = random_target_within(DUNG_HOLE_REGION)
    logger.info(f"🎯 Moving to dung hole: ({tx}, {ty})")
    human_move(tx, ty)
    
    if not running:
        return False
    
    # Pre-click micro-adjustment
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.8, 0.8), 
                     current_y + random.uniform(-0.8, 0.8))
    
    # Brief pre-click pause
    time.sleep(random.uniform(0.03, 0.12))
    
    # Perform click
    mouse.click(Button.left, 1)
    click_count += 1
    session_stats['total_dung_clicks'] += 1
    
    logger.info(f"✅ Dung hole click #{click_count} completed at ({mouse.position[0]:.0f}, {mouse.position[1]:.0f})")
    return True

def smart_wait(wait_time, action_description="next action"):
    """
    Wait for the specified time with smart progress updates.
    Memory-optimized version that minimizes logging and uses efficient sleep.
    """
    if wait_time <= 30:
        # For short waits, use single sleep to minimize memory overhead
        end_time = time.time() + wait_time
        while running and time.time() < end_time:
            time.sleep(min(5, wait_time))  # Use longer sleep intervals
        return
    
    # For longer waits, show initial message only
    logger.info(f"⏰ Waiting {wait_time:.1f}s until {action_description}...")
    
    end_time = time.time() + wait_time
    last_progress_time = time.time()
    
    while running and time.time() < end_time:
        remaining = end_time - time.time()
        current_time = time.time()
        
        # Show progress only if explicitly enabled and at long intervals
        if (SHOW_DETAILED_PROGRESS and 
            current_time - last_progress_time >= PROGRESS_UPDATE_INTERVAL and 
            remaining > 60):
            
            minutes = int(remaining // 60)
            # Force immediate flush after logging
            logger.info(f"⏳ {minutes}m remaining until {action_description}...")
            logger.handlers[0].flush()
            last_progress_time = current_time
        
        # Use longer sleep intervals to reduce memory pressure
        if remaining > 120:
            time.sleep(30)  # 30 second intervals for very long waits
        elif remaining > 60:
            time.sleep(15)  # 15 second intervals for medium waits
        elif remaining > 30:
            time.sleep(10)  # 10 second intervals for shorter waits
        else:
            time.sleep(2)   # 2 second intervals for final countdown

# ─── Core click loop ───────────────────────────────────────────────────────────
def click_loop():
    global click_count, running, session_stats

    settings = get_current_settings()
    
    logger.info("🚀 Entering click loop. Press '`' to stop, '~' to exit.")
    logger.info(f"🎮 Mode: {settings['mode']}")
    logger.info(f"🕳️  Dung Hole Region: {DUNG_HOLE_REGION}")
    logger.info(f"🍋 Lemon Sour Region: {LEMON_SOUR_REGION}")
    if USE_HOLE_IN_ONE:
        logger.info(f"🏌️  Hole in One Region: {HOLE_IN_ONE_REGION}")
    
    # Initial delay for user to switch screens
    logger.info(f"⏳ Initial delay: {INITIAL_DELAY_SEC} seconds to switch screens...")
    for i in range(INITIAL_DELAY_SEC, 0, -1):
        if not running:  # Allow stopping during countdown
            logger.info("⏹️  Startup cancelled.")
            return
        logger.info(f"⏳ Starting in {i} seconds...")
        time.sleep(1)
    
    logger.info("🎯 Starting automation NOW!")
    
    # Start with cocktail sequence
    logger.info("🍹 Starting with cocktail sequence...")
    if not click_cocktails():
        return
    
    # Wait between cocktails and first dung hole click
    smart_wait(random.uniform(2.5, 7.5), "first dung hole click")
    
    dung_hole_count = 0
    
    while running:
        try:
            # Click dung hole
            if not click_dung_hole():
                break
            
            dung_hole_count += 1
            
            # Show stats every 5 dung hole clicks
            if dung_hole_count % 5 == 0:
                print_stats()
                # Force garbage collection after stats to free memory
                if FORCE_GARBAGE_COLLECTION:
                    gc.collect()
            
            # Wait for character to exit dung hole + buffer time
            min_wait, max_wait = settings['dung_hole_duration']
            interval = random.uniform(min_wait, max_wait)
            
            if USE_HOLE_IN_ONE:
                smart_wait(interval, "character to exit dung hole (Hole in One mode)")
            else:
                smart_wait(interval, "character to exit dung hole")
            
            # Check if we need to click cocktails again
            if dung_hole_count % settings['cocktail_interval'] == 0:
                session_stats['cocktail_cycles'] += 1
                logger.info(f"🔄 Cycle #{session_stats['cocktail_cycles']}: Time for cocktail sequence!")
                
                if not click_cocktails():
                    break
                
                # Wait between cocktails and next dung hole click
                smart_wait(random.uniform(2.5, 7.5), "next dung hole click")
            
            # Occasional human break
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

# ─── Key listener ──────────────────────────────────────────────────────────────
def on_press(key):
    global running, click_thread, session_stats
    try:
        if key == START_STOP_KEY:
            if not running:
                # Starting
                running = True
                session_stats['session_start'] = time.time()
                logger.info("▶️  AUTOMATION STARTED")
                logger.info(f"🎮 Controls: Press '`' to stop, '~' to exit")
                click_thread = threading.Thread(target=click_loop, daemon=True)
                click_thread.start()
            else:
                # Stopping
                running = False
                logger.info("⏸️  AUTOMATION PAUSED")
                if click_thread and click_thread.is_alive():
                    logger.info("⏳ Waiting for current action to complete...")
                    click_thread.join(timeout=5)
                print_stats()
                logger.info(f"🎮 Press '`' to resume, '~' to exit")
                
        elif key == EXIT_KEY:
            logger.info("🛑 EXIT REQUESTED")
            running = False
            if click_thread and click_thread.is_alive():
                logger.info("⏳ Waiting for automation to stop...")
                click_thread.join(timeout=5)
            print_stats()
            logger.info("👋 Goodbye!")
            listener.stop()
            
    except Exception as e:
        logger.error(f"❌ Error in key handler: {e}")

# ─── Entry point ───────────────────────────────────────────────────────────────
def main():
    settings = get_current_settings()
    platform_info = get_platform_info()
    
    logger.info("🎮 Enhanced Anti-Bot Mouse Automation Script")
    logger.info("=" * 60)
    logger.info(f"💻 Platform: {platform_info['platform']}")
    logger.info(f"🎮 Mode: {settings['mode']}")
    logger.info(f"⌨️  START/STOP: Press '`' (backtick)")
    logger.info(f"⌨️  EXIT: Press '~' (tilde)")
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
    logger.info(f"🕳️  Dung Hole Region: {platform_info['dung_hole']}")
    logger.info(f"🍋 Lemon Sour Region: {platform_info['lemon_sour']}")
    if USE_HOLE_IN_ONE:
        logger.info(f"🏌️  Hole in One Region: {platform_info['hole_in_one']}")
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
    
    try:
        with Listener(on_press=on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()