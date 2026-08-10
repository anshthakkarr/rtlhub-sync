import os
import shutil
import time
from playwright.sync_api import sync_playwright

SESSION_DIR = "./rtlhub_session"

# Wipe the entire session folder to clear disk cache, localStorage, and IndexedDB
print("Clearing old session and local cache...")
if os.path.exists(SESSION_DIR):
    try:
        shutil.rmtree(SESSION_DIR)
        print("-> Old session cleared.")
    except Exception as e:
        print(f"[!] Warning: Could not delete session directory: {e}")

# Launch browser to perform a fresh login
with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=SESSION_DIR,
        headless=False,
        no_viewport=True,
        args=["--start-maximized"]
    )
    
    page = context.pages[0] if context.pages else context.new_page()
    print("Navigating to RTLHub login...")
    page.goto("https://rtlhub.com")

    print("\n=======================================================")
    print("1. Log in to RTLHub in the browser window.")
    print("2. Make sure you can see the Problems page.")
    print("3. Return here and press ENTER to save your fresh session.")
    print("=======================================================\n")

    input("Press ENTER after logging in...")
    
    context.close()
    print("\nFresh session saved to ./rtlhub_session!")
    print("You can now run `python3 sync_rtlhub.py`.")
