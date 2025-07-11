import time  # Importing the time module for sleep and time-related functions
import random  # Importing the random module for generating random numbers
import logging  # Importing the logging module for logging messages
import sys  # Importing the sys module for system-specific parameters and functions
import threading  # Importing the threading module for creating and managing threads
import pyautogui  # Importing the pyautogui module for GUI automation
from pynput.keyboard import Listener, KeyCode  # Importing Listener and KeyCode from pynput for keyboard event handling

# Setup logging to output to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)

# Activation keys
START_STOP_KEY = KeyCode(char='-')  # Key to start/stop the script
EXIT_KEY = KeyCode(char='+')  # Key to exit the script (+ key)

# Configuration
INITIAL_DELAY = 10  # Initial delay before the first click (seconds)
CLICK_INTERVAL_MIN = 55  # Minimum interval between clicks (seconds)
CLICK_INTERVAL_MAX = 68  # Maximum interval between clicks (seconds)
POST_CLICK_DELAY = 3  # Delay after each click (seconds)

# Global state
running = False  # Flag to indicate if the script is running
click_count = 0  # Counter for the number of clicks made
click_thread = None  # Thread for the click loop
lock = threading.Lock()  # Lock for thread synchronization

def on_press(key):
    global running, click_thread
    try:
        if key == START_STOP_KEY:  # Check if the start/stop key is pressed
            with lock:
                running = not running  # Toggle the running state
            if running:
                logging.info("Script started.")
                click_thread = threading.Thread(target=click_loop)  # Create a new thread for the click loop
                click_thread.start()  # Start the click loop thread
            else:
                logging.info("Script stopped.")
        elif key == EXIT_KEY:  # Check if the exit key is pressed
            logging.info(f"Exiting script. Total clicks made: {click_count}")
            with lock:
                running = False  # Stop the script
            if click_thread:
                click_thread.join()  # Wait for the click loop thread to finish
            listener.stop()  # Stop the keyboard listener
    except Exception as e:
        logging.error(f"Error in on_press: {e}")

def click_loop():
    global click_count, running
    try:
        logging.info(f"Initial delay of {INITIAL_DELAY} seconds before first click.")
        time.sleep(INITIAL_DELAY)  # Wait for the initial delay

        while True:
            with lock:
                if not running:
                    logging.info("Script is not running. Exiting click loop.")
                    break  # Exit the loop if the script is not running
            try:
                logging.info("Starting click sequence.")
                perform_click_sequence()  # Perform the click sequence
            except Exception as e:
                logging.error(f"Error during click loop iteration: {e}")
                with lock:
                    running = False  # Stop the script if an error occurs
    except Exception as e:
        logging.error(f"Error in click_loop: {e}")
        with lock:
            running = False  # Stop the script if an error occurs

def perform_click_sequence():
    global click_count
    try:
        # click("Palmer Farmer", 1698, random.randint(802, 812))  # Click on "Palmer Farmer"
        # time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay
        # click("Pineappletini", 1698, random.randint(840, 850))  # Click on "Pineappletini"
        # time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay

        # Calculate the end time for the 14-minute interval
        end_time = time.time() + 13 * 60 + random.randint(10, 20)
        logging.info(f"End time set to {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")

        # Start a separate thread for pressing the "1" key
        def press_key_loop(end_time):
            while time.time() < end_time:
                with lock:
                    if not running:
                        logging.info("Script is not running. Exiting 1 key press loop.")
                        return  # Exit the loop if the script is not running
                pyautogui.press('1')  # Press the "1" key
                logging.info("Pressing '1' key.")
                time.sleep(2)  # Wait for 2 seconds

        key_press_thread = threading.Thread(target=press_key_loop, args=(end_time,))
        key_press_thread.start()

        while time.time() < end_time:
            with lock:
                if not running:
                    logging.info("Script is not running. Exiting click sequence.")
                    return  # Exit the loop if the script is not running
            click("Palm Tree", random.randint(815, 850), random.randint(375, 430))  # Click on "Palm Tree"
            interval = random.uniform(CLICK_INTERVAL_MIN, CLICK_INTERVAL_MAX)
            time.sleep(interval)  # Wait for a random interval between clicks
            time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay

        time.sleep(POST_CLICK_DELAY)  # Wait for the post-click delay
        logging.info("14 minutes interval completed. Restarting drink sequence.")
    except Exception as e:
        logging.error(f"Error in perform_click_sequence: {e}")

def click(description, x, y):
    global click_count
    pyautogui.moveTo(x, y)  # Move the mouse to the specified coordinates
    pyautogui.click()  # Perform a mouse click
    click_count += 1  # Increment the click count
    logging.info(f"Clicked {description}. Total clicks: {click_count}")

try:
    with Listener(on_press=on_press) as listener:  # Start the keyboard listener
        logging.info("Listener started. Press '-' to start/stop and '+' to exit.")
        listener.join()  # Wait for the listener to stop
except Exception as e:
    logging.error(f"Error starting listener: {e}")