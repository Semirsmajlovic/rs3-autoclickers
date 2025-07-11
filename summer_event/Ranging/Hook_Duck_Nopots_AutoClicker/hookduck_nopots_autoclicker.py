import time
import random
import logging
import sys
import threading
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Listener, KeyCode

# Setup logging to output to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

mouse = MouseController()

# Activation keys
START_STOP_KEY = KeyCode(char='-')
EXIT_KEY = KeyCode(char='+')

# Configuration
INITIAL_DELAY = 10  # Initial delay before the first click (seconds)
CLICK_INTERVAL_MIN = 55  # Minimum interval between clicks (seconds)
CLICK_INTERVAL_MAX = 68  # Maximum interval between clicks (seconds)
POST_CLICK_DELAY = 3  # Delay after each click (seconds)

running = False
click_count = 0
click_thread = None

def on_press(key):
    global running, click_thread
    try:
        if key == START_STOP_KEY:
            running = not running
            if running:
                logging.info("Script started.")
                click_thread = threading.Thread(target=click_loop)
                click_thread.start()
            else:
                logging.info("Script stopped.")
        elif key == EXIT_KEY:
            logging.info(f"Exiting script. Total clicks made: {click_count}")
            running = False
            if click_thread:
                click_thread.join()
            listener.stop()
    except Exception as e:
        logging.error(f"Error in on_press: {e}")

def click_loop():
    global click_count, running
    try:
        logging.info(f"Initial delay of {INITIAL_DELAY} seconds before first click.")
        time.sleep(INITIAL_DELAY)
        while running:
            # Move to the first position and click
            mouse.position = (1696, random.randint(844, 848))
            time.sleep(0.1)  # Small delay to ensure the mouse has moved
            mouse.click(Button.left, 1)
            logging.info(f"Clicked Pineappletini @ {time}")
            time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay

            # Move to the second position and click
            x_move = random.randint(795, 910)
            y_move = random.randint(170, 280)
            mouse.position = (x_move, y_move)
            time.sleep(0.1)  # Small delay to ensure the mouse has moved
            mouse.click(Button.left, 1)
            click_count += 1
            time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay

            logging.info(f"Clicked Hook a Duck at ({x_move}, {y_move}). Total clicks: {click_count}")
            time.sleep(random.uniform(CLICK_INTERVAL_MIN, CLICK_INTERVAL_MAX))
            time.sleep(POST_CLICK_DELAY)
    except Exception as e:
        logging.error(f"Error in click_loop: {e}")
        running = False

# def click_loop():
#     global click_count, running
#     try:
#         logging.info(f"Initial delay of {INITIAL_DELAY} seconds before first click.")
#         time.sleep(INITIAL_DELAY)
#         while running:
#             x_move = random.randint(795, 910)
#             y_move = random.randint(170, 280)
#             mouse.position = (x_move, y_move)
#             mouse.click(Button.left, 1)
#             click_count += 1
#             time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay
#             logging.info(f"Clicked Hook a Duck at ({x_move}, {y_move}). Total clicks: {click_count}")
#             time.sleep(random.uniform(CLICK_INTERVAL_MIN, CLICK_INTERVAL_MAX))
#             time.sleep(POST_CLICK_DELAY)
#     except Exception as e:
#         logging.error(f"Error in click_loop: {e}")
#         running = False

with Listener(on_press=on_press) as listener:
    listener.join()