import time
import random
import logging
import sys
import threading
import math
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Listener, KeyCode

# ─── Configuration ────────────────────────────────────────────────────────────
START_STOP_KEY    = KeyCode(char='`')  # Backtick/grave accent key
EXIT_KEY          = KeyCode(char='~')  # Tilde key
DUNG_HOLE_REGION  = (830, 605, 895, 670)  # (x_min, y_min, x_max, y_max)
LEMON_SOUR_REGION = (1680, 875, 1705, 900)  # Lemon Sour cocktail coordinates
HOLE_IN_ONE_REGION = (1680, 840, 1705, 865)  # Hole in One cocktail coordinates (adjust as needed)
MIN_CLICKS_BEFORE_BREAK = 20
BREAK_MIN_SEC     = 5
BREAK_MAX_SEC     = 15
INITIAL_DELAY_SEC = 10  # Delay before first click starts

# ─── Hole in One Configuration ────────────────────────────────────────────────
USE_HOLE_IN_ONE = True  # Set to True to enable Hole in One cocktail, False to disable
COCKTAIL_INTERVAL_NORMAL = 10  # Click cocktails every X dung hole cycles (without Hole in One)
COCKTAIL_INTERVAL_HOLE_IN_ONE = 4  # Click cocktails every X dung hole cycles (with Hole in One)
DUNG_HOLE_DURATION_NORMAL = (77, 90)  # Wait time without Hole in One (77-90 seconds)
DUNG_HOLE_DURATION_HOLE_IN_ONE = (232, 242)  # Wait time with Hole in One (3:52-4:02 minutes)

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

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(ColoredFormatter('%(asctime)s - %(levelname)s - %(message)s'))
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

# ─── Human-like movement helpers ───────────────────────────────────────────────

def ease_out_quad(t: float) -> float:
    """Quadratic ease-out: fast start, slow end."""
    return 1 - (1 - t) * (1 - t)

def human_move(to_x: int, to_y: int):
    """
    Move mouse from current position to (to_x, to_y)
    using smooth easing and micro-jitter.
    """
    global session_stats
    start_x, start_y = mouse.position
    dist_x, dist_y = to_x - start_x, to_y - start_y
    distance = math.hypot(dist_x, dist_y)

    if distance < 2:  # Already close enough
        return

    # Choose number of steps proportional to distance
    steps = int(max(8, min(25, distance / 3)))
    
    logger.debug(f"Moving from ({start_x:.0f}, {start_y:.0f}) to ({to_x}, {to_y}) - Distance: {distance:.1f}px in {steps} steps")
    
    for i in range(steps):
        if not running:  # Allow stopping mid-movement
            break
            
        t = (i + 1) / steps
        t_eased = ease_out_quad(t)
        
        # Calculate target position
        cur_x = start_x + dist_x * t_eased
        cur_y = start_y + dist_y * t_eased
        
        # Add micro-jitter (less at the end)
        jitter_strength = (1 - t) * 0.5
        jitter_x = random.uniform(-jitter_strength, jitter_strength)
        jitter_y = random.uniform(-jitter_strength, jitter_strength)
        
        # Set absolute position
        mouse.position = (cur_x + jitter_x, cur_y + jitter_y)
        
        # Variable sleep per step
        time.sleep(random.uniform(0.005, 0.015))
    
    # Final position adjustment
    mouse.position = (to_x, to_y)
    session_stats['total_moves'] += 1
    
    # Small pause as if deciding
    time.sleep(random.uniform(0.05, 0.15))

def random_target_within(region):
    """Return a random (x,y) inside the given region with a tiny inset."""
    x_min, y_min, x_max, y_max = region
    inset = 4  # avoid perfect corners
    x = random.randint(x_min + inset, x_max - inset)
    y = random.randint(y_min + inset, y_max - inset)
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
    
    # Final tiny jitter before click
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.5, 0.5), 
                     current_y + random.uniform(-0.5, 0.5))
    
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
    
    # Final tiny jitter before click
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.5, 0.5), 
                     current_y + random.uniform(-0.5, 0.5))
    
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
            
        # Wait between cocktails
        delay = random.uniform(3, 8)
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
    
    # Final tiny jitter before click
    current_x, current_y = mouse.position
    mouse.position = (current_x + random.uniform(-0.5, 0.5), 
                     current_y + random.uniform(-0.5, 0.5))
    
    # Perform click
    mouse.click(Button.left, 1)
    click_count += 1
    session_stats['total_dung_clicks'] += 1
    
    logger.info(f"✅ Dung hole click #{click_count} completed at ({mouse.position[0]:.0f}, {mouse.position[1]:.0f})")
    return True

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
    delay = random.uniform(3, 8)  # 3-8 seconds between cocktails and dung hole
    logger.info(f"⏳ Waiting {delay:.1f}s before first dung hole click...")
    end_time = time.time() + delay
    while running and time.time() < end_time:
        time.sleep(0.5)
    
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
            
            # Wait for character to exit dung hole + buffer time
            min_wait, max_wait = settings['dung_hole_duration']
            interval = random.uniform(min_wait, max_wait)
            
            if USE_HOLE_IN_ONE:
                logger.info(f"⏰ Waiting {interval:.1f}s for character to exit dung hole (Hole in One mode - 4+ minutes)...")
            else:
                logger.info(f"⏰ Waiting {interval:.1f}s for character to exit dung hole + buffer...")
            
            # Sleep in small chunks to allow responsive stopping
            end_time = time.time() + interval
            while running and time.time() < end_time:
                remaining = end_time - time.time()
                if remaining > 30:  # Show progress for longer waits
                    minutes = int(remaining // 60)
                    seconds = int(remaining % 60)
                    if minutes > 0:
                        logger.info(f"⏳ {minutes}m {seconds}s remaining until next action...")
                    else:
                        logger.info(f"⏳ {seconds}s remaining until next action...")
                time.sleep(10 if remaining > 60 else 5 if remaining > 30 else 0.5)
            
            # Check if we need to click cocktails again
            if dung_hole_count % settings['cocktail_interval'] == 0:
                session_stats['cocktail_cycles'] += 1
                logger.info(f"🔄 Cycle #{session_stats['cocktail_cycles']}: Time for cocktail sequence!")
                
                if not click_cocktails():
                    break
                
                # Wait between cocktails and next dung hole click
                delay = random.uniform(3, 8)
                logger.info(f"⏳ Waiting {delay:.1f}s before next dung hole click...")
                end_time = time.time() + delay
                while running and time.time() < end_time:
                    time.sleep(0.5)
            
            # Occasional human break
            if click_count % MIN_CLICKS_BEFORE_BREAK == 0:
                break_duration = random.uniform(BREAK_MIN_SEC, BREAK_MAX_SEC)
                session_stats['total_breaks'] += 1
                logger.info(f"☕ Taking break #{session_stats['total_breaks']} for {break_duration:.1f}s to stretch...")
                
                # Sleep in chunks for responsive stopping
                end_break = time.time() + break_duration
                while running and time.time() < end_break:
                    time.sleep(0.5)
                
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
    
    logger.info("🎮 Mouse Automation Script")
    logger.info("=" * 60)
    logger.info(f"🎮 Mode: {settings['mode']}")
    logger.info(f"⌨️  START/STOP: Press '`' (backtick)")
    logger.info(f"⌨️  EXIT: Press '~' (tilde)")
    logger.info("─" * 60)
    logger.info(f"🕳️  Dung Hole Region: {DUNG_HOLE_REGION}")
    logger.info(f"🍋 Lemon Sour Region: {LEMON_SOUR_REGION}")
    if USE_HOLE_IN_ONE:
        logger.info(f"🏌️  Hole in One Region: {HOLE_IN_ONE_REGION}")
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
    logger.info("=" * 60)
    
    if USE_HOLE_IN_ONE:
        logger.info("🏌️  HOLE IN ONE MODE ACTIVE - Extended 4+ minute dung hole duration!")
    else:
        logger.info("🍋 NORMAL MODE - Standard 1:15 minute dung hole duration")
    
    logger.info("💡 Ready! Press '`' (backtick) to start automation...")
    
    try:
        with Listener(on_press=on_press) as listener:
            listener.join()
    except KeyboardInterrupt:
        logger.info("👋 Script interrupted by user")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")

if __name__ == "__main__":
    main()