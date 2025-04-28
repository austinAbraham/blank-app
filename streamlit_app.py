import streamlit as st
import time
import random
import threading
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime, timedelta
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import streamlit.components.v1 as components
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("dvsa_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
LOGIN_URL = 'https://driverpracticaltest.dvsa.gov.uk/login'

# User agent list for rotation
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.71 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36'
]

# Global variables
bot_thread = None
stop_event = threading.Event()
log_queue = []
status_placeholder = None
last_check_time = None
next_check_time = None
bot_status = "Stopped"

def send_notification(subject, message, email_config):
    """Send email notification"""
    if not all([email_config["email_user"], email_config["email_password"], email_config["notification_email"]]):
        logger.warning("Email configuration incomplete. Skipping notification.")
        return False
        
    try:
        msg = MIMEMultipart()
        msg['From'] = email_config["email_user"]
        msg['To'] = email_config["notification_email"]
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'plain'))
        
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_config["email_user"], email_config["email_password"])
        server.send_message(msg)
        server.quit()
        
        logger.info("Notification email sent successfully")
        log_message("Notification email sent successfully")
        return True
    except Exception as e:
        error_msg = f"Failed to send notification: {str(e)}"
        logger.error(error_msg)
        log_message(error_msg, "error")
        return False

def format_date(date):
    """Format date for display"""
    return date.strftime("%A, %d %B %Y")

def parse_date(date_string):
    """Parse date string to datetime object"""
    return datetime.strptime(date_string, "%Y-%m-%d")

def setup_driver(use_proxy=False, proxy_address="", use_user_agent_rotation=True):
    """Set up and configure the WebDriver"""
    chrome_options = Options()
    
    # Configure for cloud deployment
    if not st.session_state.get('debug_mode', False):
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
    
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    # Random user agent rotation if enabled
    if use_user_agent_rotation:
        user_agent = random.choice(USER_AGENTS)
        chrome_options.add_argument(f'user-agent={user_agent}')
        logger.info(f"Using user agent: {user_agent}")
        log_message(f"Using user agent: {user_agent}")
    
    # Add proxy if configured
    if use_proxy and proxy_address:
        chrome_options.add_argument(f'--proxy-server={proxy_address}')
        logger.info(f"Using proxy: {proxy_address}")
        log_message(f"Using proxy: {proxy_address}")
    
    # Add additional fingerprint randomization
    chrome_options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # Create WebDriver
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set random window size to avoid detection
        width = random.randint(1050, 1200)
        height = random.randint(800, 950)
        driver.set_window_size(width, height)
        
        return driver
    except Exception as e:
        error_msg = f"Failed to set up WebDriver: {str(e)}"
        logger.error(error_msg)
        log_message(error_msg, "error")
        return None

def humanized_delay(min_seconds=1, max_seconds=3):
    """Add random delay to simulate human behavior"""
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)

def log_message(message, level="info"):
    """Add message to log queue for display"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_queue.append({"time": timestamp, "message": message, "level": level})
    
    # Keep log queue at a reasonable size
    while len(log_queue) > 100:
        log_queue.pop(0)

def check_for_better_dates(config):
    """Main function to check for better test dates"""
    global last_check_time, next_check_time, bot_status
    
    last_check_time = datetime.now()
    bot_status = "Running"
    log_message(f"Starting date check at {last_check_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    driver = None
    try:
        driver = setup_driver(
            use_proxy=config["use_proxy"],
            proxy_address=config["proxy_address"],
            use_user_agent_rotation=config["use_user_agent_rotation"]
        )
        
        if not driver:
            raise Exception("Failed to initialize WebDriver")
        
        # Navigate to login page with randomized timing
        log_message("Navigating to login page...")
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "driving-licence-number"))
        )
        humanized_delay(2, 4)
        
        # Login process with human-like typing and delays
        log_message("Logging in...")
        
        # Enter driving license number with human-like typing
        license_input = driver.find_element(By.ID, "driving-licence-number")
        for char in config["username"]:
            license_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
        humanized_delay()
        
        # Enter reference number with human-like typing
        reference_input = driver.find_element(By.ID, "application-reference-number")
        for char in config["password"]:
            reference_input.send_keys(char)
            time.sleep(random.uniform(0.05, 0.2))
        humanized_delay()
        
        # Click login button and wait for navigation
        driver.find_element(By.ID, "booking-login").click()
        humanized_delay(3, 5)
        
        # Check for login errors
        try:
            error_element = driver.find_element(By.CLASS_NAME, "error-summary")
            error_message = error_element.text
            raise Exception(f"Login failed: {error_message}")
        except NoSuchElementException:
            # No error found, continue
            log_message("Login successful")
            
        # Navigate to 'Change booking' section
        log_message("Navigating to change booking section...")
        try:
            change_booking_links = driver.find_elements(By.XPATH, "//a[contains(@href, 'change')]")
            if change_booking_links:
                change_booking_links[0].click()
                humanized_delay(2, 4)
            else:
                raise Exception("Change booking link not found")
            
            # Click on 'Change test date' button
            change_date_links = driver.find_elements(By.XPATH, "//a[contains(text(), 'Change test date')]")
            if change_date_links:
                change_date_links[0].click()
                humanized_delay(2, 4)
            else:
                raise Exception("Change test date button not found")
            
            # Parse current appointment date
            current_appointment_date = parse_date(config["current_test_date"])
            log_message(f"Current appointment date: {format_date(current_appointment_date)}")
            
            # Check for available dates
            log_message("Checking for available dates...")
            
            # Wait for available dates to load
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "BookingCalendar-date--bookable"))
            )
            humanized_delay()
            
            # Get all available dates
            available_dates = []
            date_elements = driver.find_elements(By.CLASS_NAME, "BookingCalendar-date--bookable")
            
            for element in date_elements:
                date_str = element.get_attribute("data-date")
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                        available_dates.append({"date_string": date_str, "date": date_obj, "element": element})
                    except ValueError:
                        continue
            
            log_message(f"Found {len(available_dates)} available dates")
            
            # Filter for dates earlier than current appointment
            earlier_dates = [
                date_info for date_info in available_dates 
                if date_info["date"] < current_appointment_date
            ]
            earlier_dates.sort(key=lambda x: x["date"])  # Sort by earliest first
            
            log_message(f"Found {len(earlier_dates)} earlier dates")
            
            if earlier_dates:
                # Best date is the earliest one
                best_date = earlier_dates[0]
                log_message(f"Found better date: {format_date(best_date['date'])}", "success")
                
                if config["auto_book"]:
                    # Click on the best date
                    best_date["element"].click()
                    humanized_delay(2, 3)
                    
                    # Wait for time slots to appear
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "SlotPicker-day"))
                    )
                    humanized_delay()
                    
                    # Select the first available time slot
                    time_slots = driver.find_elements(
                        By.XPATH, "//li[contains(@class, 'SlotPicker-slot') and not(contains(@class, 'SlotPicker-slot--unavailable'))]"
                    )
                    
                    if time_slots:
                        selected_slot = time_slots[0]
                        slot_time = selected_slot.text.strip()
                        selected_slot.click()
                        humanized_delay(1, 2)
                        
                        # Confirm slot selection
                        confirm_buttons = driver.find_elements(By.ID, "slot-chosen-submit")
                        if confirm_buttons:
                            confirm_buttons[0].click()
                            humanized_delay(3, 5)
                            
                            # Final confirmation on review page
                            final_confirm_buttons = driver.find_elements(By.ID, "confirm-changes")
                            if final_confirm_buttons:
                                final_confirm_buttons[0].click()
                                humanized_delay(5, 7)
                                
                                # Check for success message
                                try:
                                    success_element = WebDriverWait(driver, 10).until(
                                        EC.presence_of_element_located((By.CLASS_NAME, "confirmation-message"))
                                    )
                                    
                                    new_date_details = success_element.text
                                    
                                    # Send notification about successful rebooking
                                    success_message = f"""Successfully rebooked your driving test!

New test date: {format_date(best_date['date'])} at {slot_time}

Previous test date: {format_date(current_appointment_date)}

Details: {new_date_details}
"""
                                    send_notification(
                                        "DVSA Test Successfully Rebooked!", 
                                        success_message,
                                        {
                                            "email_user": config["email_user"],
                                            "email_password": config["email_password"],
                                            "notification_email": config["notification_email"]
                                        }
                                    )
                                    log_message("Successfully rebooked test!", "success")
                                    
                                    # Update the current test date in session state
                                    st.session_state.current_test_date = best_date["date_string"]
                                    
                                except (TimeoutException, NoSuchElementException):
                                    log_message("Could not confirm successful booking", "error")
                            else:
                                log_message("Final confirmation button not found", "error")
                        else:
                            log_message("Slot confirmation button not found", "error")
                    else:
                        log_message("No time slots available for the selected date", "warning")
                else:
                    # Just notification mode
                    notification_message = f"""Earlier test date found!

Available date: {format_date(best_date['date'])}

Your current date: {format_date(current_appointment_date)}

Log in to the DVSA website to book this date manually.
"""
                    send_notification(
                        "DVSA Earlier Test Date Available!", 
                        notification_message,
                        {
                            "email_user": config["email_user"],
                            "email_password": config["email_password"],
                            "notification_email": config["notification_email"]
                        }
                    )
            else:
                log_message("No earlier dates found")
                
        except Exception as e:
            error_msg = f"Error during navigation: {str(e)}"
            logger.error(error_msg)
            log_message(error_msg, "error")
            
    except Exception as e:
        error_msg = f"Error during date check: {str(e)}"
        logger.error(error_msg)
        log_message(error_msg, "error")
        send_notification(
            "DVSA Bot Error", 
            error_msg,
            {
                "email_user": config["email_user"],
                "email_password": config["email_password"],
                "notification_email": config["notification_email"]
            }
        )
    finally:
        if driver:
            driver.quit()
        
        # Update status for next check
        interval = random.randint(
            config["check_interval_min"] * 60, 
            config["check_interval_max"] * 60
        )
        next_check_time = datetime.now() + timedelta(seconds=interval)
        log_message(f"Next check scheduled at {next_check_time.strftime('%H:%M:%S')} (in {interval//60} minutes)")

def bot_loop(config):
    """Main bot loop that runs in a separate thread"""
    global bot_status, next_check_time
    
    log_message("Bot started")
    bot_status = "Running"
    
    while not stop_event.is_set():
        try:
            # Run the check
            check_for_better_dates(config)
            
            # Calculate random interval for next check (in seconds)
            interval = random.randint(
                config["check_interval_min"] * 60, 
                config["check_interval_max"] * 60
            )
            
            # Wait for the interval or until stopped
            countdown_start = time.time()
            while time.time() - countdown_start < interval:
                if stop_event.is_set():
                    break
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Unexpected error in bot loop: {str(e)}")
            log_message(f"Unexpected error: {str(e)}", "error")
            time.sleep(60)  # Wait a minute before retrying
    
    bot_status = "Stopped"
    log_message("Bot stopped")

def start_bot():
    """Start the bot in a separate thread"""
    global bot_thread, stop_event
    
    if bot_thread and bot_thread.is_alive():
        st.warning("Bot is already running!")
        return
    
    # Reset stop event
    stop_event.clear()
    
    # Get configuration from session state
    config = {
        "username": st.session_state.username,
        "password": st.session_state.password,
        "current_test_date": st.session_state.current_test_date,
        "check_interval_min": st.session_state.check_interval_min,
        "check_interval_max": st.session_state.check_interval_max,
        "email_user": st.session_state.email_user,
        "email_password": st.session_state.email_password,
        "notification_email": st.session_state.notification_email,
        "use_proxy": st.session_state.use_proxy,
        "proxy_address": st.session_state.proxy_address,
        "use_user_agent_rotation": st.session_state.use_user_agent_rotation,
        "auto_book": st.session_state.auto_book
    }
    
    # Validate config
    if not all([config["username"], config["password"], config["current_test_date"]]):
        st.error("Please fill in all required fields (username, password, and current test date)")
        return
    
    try:
        # Parse date to validate format
        parse_date(config["current_test_date"])
    except ValueError:
        st.error("Invalid date format. Please use YYYY-MM-DD format for the current test date.")
        return
    
    # Start bot thread
    bot_thread = threading.Thread(target=bot_loop, args=(config,))
    bot_thread.daemon = True
    bot_thread.start()
    
    st.success("Bot started successfully!")

def stop_bot():
    """Stop the bot thread"""
    global stop_event
    
    if bot_thread and bot_thread.is_alive():
        stop_event.set()
        log_message("Stopping bot... (this may take a moment)")
        st.success("Bot is shutting down...")
    else:
        st.warning("Bot is not running!")

def run_manual_check():
    """Run a one-time check"""
    # Get configuration from session state
    config = {
        "username": st.session_state.username,
        "password": st.session_state.password,
        "current_test_date": st.session_state.current_test_date,
        "check_interval_min": st.session_state.check_interval_min,
        "check_interval_max": st.session_state.check_interval_max,
        "email_user": st.session_state.email_user,
        "email_password": st.session_state.email_password,
        "notification_email": st.session_state.notification_email,
        "use_proxy": st.session_state.use_proxy,
        "proxy_address": st.session_state.proxy_address,
        "use_user_agent_rotation": st.session_state.use_user_agent_rotation,
        "auto_book": st.session_state.auto_book
    }
    
    # Validate config
    if not all([config["username"], config["password"], config["current_test_date"]]):
        st.error("Please fill in all required fields (username, password, and current test date)")
        return
    
    try:
        # Parse date to validate format
        parse_date(config["current_test_date"])
    except ValueError:
        st.error("Invalid date format. Please use YYYY-MM-DD format for the current test date.")
        return
    
    # Clear stop event in case it was set
    stop_event.clear()
    
    # Run the check in a separate thread
    check_thread = threading.Thread(target=check_for_better_dates, args=(config,))
    check_thread.daemon = True
    check_thread.start()
    
    st.success("Manual check started!")

def test_notification():
    """Test email notification"""
    config = {
        "email_user": st.session_state.email_user,
        "email_password": st.session_state.email_password,
        "notification_email": st.session_state.notification_email
    }
    
    if not all([config["email_user"], config["email_password"], config["notification_email"]]):
        st.error("Please fill in all email configuration fields")
        return
    
    success = send_notification(
        "DVSA Bot Test Notification",
        "This is a test notification from your DVSA Bot. If you received this, your email configuration is working correctly!",
        config
    )
    
    if success:
        st.success("Test notification sent successfully!")
    else:
        st.error("Failed to send test notification. Please check your email configuration.")

def initialize_session_state():
    """Initialize session state variables with default values"""
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'password' not in st.session_state:
        st.session_state.password = ""
    if 'current_test_date' not in st.session_state:
        st.session_state.current_test_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    if 'check_interval_min' not in st.session_state:
        st.session_state.check_interval_min = 60
    if 'check_interval_max' not in st.session_state:
        st.session_state.check_interval_max = 120
    if 'email_user' not in st.session_state:
        st.session_state.email_user = ""
    if 'email_password' not in st.session_state:
        st.session_state.email_password = ""
    if 'notification_email' not in st.session_state:
        st.session_state.notification_email = ""
    if 'use_proxy' not in st.session_state:
        st.session_state.use_proxy = False
    if 'proxy_address' not in st.session_state:
        st.session_state.proxy_address = ""
    if 'use_user_agent_rotation' not in st.session_state:
        st.session_state.use_user_agent_rotation = True
    if 'auto_book' not in st.session_state:
        st.session_state.auto_book = False
    if 'debug_mode' not in st.session_state:
        st.session_state.debug_mode = False

def main():
    """Main Streamlit app"""
    global status_placeholder
    
    st.set_page_config(
        page_title="DVSA Test Date Checker",
        page_icon="🚗",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Header
    st.title("🚗 DVSA Driving Test Date Checker")
    st.markdown("""
    This app helps you find and book earlier driving test dates on the UK DVSA website.
    """)
    
    # Sidebar for configuration
    st.sidebar.title("Configuration")
    
    # DVSA Credentials
    st.sidebar.subheader("DVSA Credentials")
    st.sidebar.text_input("Driving License Number", key="username", type="password")
    st.sidebar.text_input("Application Reference Number", key="password", type="password")
    st.sidebar.date_input(
        "Current Test Date", 
        value=datetime.strptime(st.session_state.current_test_date, "%Y-%m-%d"),
        key="date_picker"
    )
    
    # Update current_test_date from date_picker
    st.session_state.current_test_date = st.session_state.date_picker.strftime("%Y-%m-%d")
    
    # Check interval settings
    st.sidebar.subheader("Check Interval")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        st.number_input("Min (minutes)", min_value=10, value=st.session_state.check_interval_min, key="check_interval_min")
    with col2:
        st.number_input("Max (minutes)", min_value=10, value=st.session_state.check_interval_max, key="check_interval_max")
    
    # Email notification settings
    st.sidebar.subheader("Email Notifications")
    st.sidebar.text_input("Gmail Address", key="email_user")
    st.sidebar.text_input("App Password", key="email_password", type="password")
    st.sidebar.text_input("Notification Email", key="notification_email")
    st.sidebar.button("Test Notification", on_click=test_notification)
    
    # Anti-detection settings
    st.sidebar.subheader("Anti-Detection Measures")
    st.sidebar.checkbox("Rotate User Agents", value=st.session_state.use_user_agent_rotation, key="use_user_agent_rotation")
    st.sidebar.checkbox("Use Proxy", value=st.session_state.use_proxy, key="use_proxy")
    if st.session_state.use_proxy:
        st.sidebar.text_input("Proxy Address (e.g., http://user:pass@host:port)", key="proxy_address")
    
    # Booking options
    st.sidebar.subheader("Booking Options")
    st.sidebar.checkbox("Auto-book Earlier Dates", value=st.session_state.auto_book, key="auto_book")
    if not st.session_state.auto_book:
        st.sidebar.info("In notification-only mode, the bot will alert you when an earlier date is found but won't book it automatically.")
    
    # Debug mode (hidden in production)
    if st.sidebar.checkbox("Debug Mode", value=st.session_state.debug_mode, key="debug_mode"):
        st.sidebar.warning("Debug mode enabled. Browser will be visible during checks.")
    
    # Create tabs for different sections
    tab1, tab2, tab3 = st.tabs(["Bot Control", "Logs", "Help"])
    
    with tab1:
        # Status indicators
        st.subheader("Bot Status")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", bot_status)
        with col2:
            if last_check_time:
                st.metric("Last Check", last_check_time.strftime("%H:%M:%S"))
            else:
                st.metric("Last Check", "Never")
        with col3:
            if next_check_time:
                st.metric("Next Check", next_check_time.strftime("%H:%M:%S"))
            else:
                st.metric("Next Check", "Not scheduled")
        
        # Control buttons
        st.subheader("Controls")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.button("Start Bot", on_click=start_bot, type="primary")
        with col2:
            st.button("Stop Bot", on_click=stop_bot, type="secondary")
        with col3:
            st.button("Run Check Now", on_click=run_manual_check)
            
        # Important information
        st.info("The bot will check for dates at random intervals to avoid detection. Keep this page open for the bot to continue running.")
        
        if not all([st.session_state.username, st.session_state.password, st.session_state.current_test_date]):
            st.warning("Please fill in all required fields in the sidebar to use the bot.")
    
    with tab2:
        # Log display
        st.subheader("Activity Log")
        
        # Create a DataFrame from log_queue for better display
        if log_queue:
            log_df = pd.DataFrame(log_queue)
            
            # Color-code based on log level
            def color_log_level(val):
                color_map = {
                    "info": "black",
                    "warning": "orange",
                    "error": "red",
                    "success": "green"
                }
                return f'color: {color_map.get(val, "black")}'
            
            # Apply styling
            styled_log = log_df.style.applymap(
                lambda x: color_log_level(x), 
                subset=["level"]
            )
            
            # Display styled log
            st.dataframe(
                styled_log,
                column_config={
                    "time": "Time",
                    "message": "Message",
                    "level": "Level"
                },
                hide_index=True,
                height=400
            )
        else:
            st.info("No log entries yet. Start the bot to see activity here.")
        
        # Add auto-refresh
        st.button("Refresh Logs")
    
    with tab3:
        # Help section
        st.subheader("How to Use")
        st.markdown("""
        ### Getting Started
        
        1. **Fill in your DVSA credentials** in the sidebar:
           - Your driving license number
           - Your application reference number
           - Your current test date
        
        2. **Set up email notifications** (highly recommended):
           - Enter your Gmail address
           - Create an App Password for your Gmail (see below)
           - Enter the email where you want to receive notifications
           - Test your notification setup
        
        3. **Configure check intervals**:
           - The bot will check at random times between your min and max settings
           - Recommended: 60-120 minutes to avoid detection
        
        4. **Choose booking mode**:
           - Auto-book: The bot will automatically book better dates
           - Notification only: The bot will just notify you when better dates are found
        
        5. **Start the bot** and keep this page open
        
        ### Creating a Gmail App Password
        
        1. Go to your Google Account at [myaccount.google.com](https://myaccount.google.com/)
        2. Select "Security" from the left menu
        3. Under "Signing in to Google," select "2-Step Verification"
        4. Scroll to the bottom and select "App passwords"
        5. Generate a new app password (select "Mail" and "Other")
        6. Copy the generated password and paste it in the "App Password" field
        
        ### Anti-Detection Features
        
        The bot includes several measures to prevent your IP from being blocked:
        
        * **User-Agent Rotation**: Changes browser fingerprint with each check
        * **Random Intervals**: Varies the time between checks
        * **Human-like Behavior**: Simulates natural typing and browsing patterns
        * **Proxy Support**: Optional use of proxy servers to hide your IP
        
        ### Tips for Success
        
        * **Use longer intervals**: 1-2 hours between checks is safer
        * **Consider using a proxy**: Especially if running 24/7
        * **Check logs regularly**: Monitor for any errors or issues
        * **Keep this tab open**: The bot runs in this browser tab
        """)
        
        st.subheader("Troubleshooting")
        st.markdown("""
        * **Login failures**: Double-check your credentials
        * **No dates found**: This is normal, keep checking
        * **Email not working**: Make sure you're using an App Password, not your regular password
        * **Bot stopped unexpectedly**: Check the logs for errors and restart
        
        If problems persist, try clearing your browser cache or using a different browser.
        """)
        
        st.subheader("Deployment Options")
        st.markdown("""
        To run this bot 24/7 without keeping your computer on:
        
        1. **Streamlit Cloud** (easiest):
           - Create a free account at [streamlit.io](https://streamlit.io/)
           - Deploy this app to Streamlit Cloud
           - Set to "Private" to protect your credentials
        
        2. **Heroku**:
           - Create a free Heroku account
           - Deploy using the Heroku CLI
           - Use a worker process to keep it running
        
        3. **Railway.app**:
           - Modern alternative to Heroku with generous free tier
           - Easy GitHub integration
        """)
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center">
        <p>DVSA Test Date Checker | Use responsibly | Not affiliated with DVSA</p>
        <p>Created for educational purposes only</p>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()