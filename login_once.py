# login_once.py
from playwright.sync_api import sync_playwright

def save_session():
    with sync_playwright() as p:
        # Launch persistent context with maximized settings
        context = p.chromium.launch_persistent_context(
            user_data_dir="./rtlhub_session",
            headless=False,
            no_viewport=True,                   # Disables default fixed resolution
            args=["--start-maximized"]          # Opens window maximized
        )
        
        # Grab the open page instead of creating a second tab
        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://rtlhub.com")
        
        print("--> Log into RTLHub via GitHub in the opened browser window.")
        print("--> Once logged in, press Enter in this terminal to save your session...")
        input()
        
        context.close()
        print("Session saved successfully!")

if __name__ == "__main__":
    save_session()