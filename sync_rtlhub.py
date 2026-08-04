import os
import time
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from github import Github, Auth, GithubException

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

if not GITHUB_TOKEN:
    raise ValueError("[!] GITHUB_TOKEN is missing! Please set it in your .env file.")

REPO_NAME = "rtlhub-solutions"

def apply_solved_filter(page):
    """Clicks the Status dropdown, selects 'Solved', and closes any dropdown menu overlay."""
    try:
        status_btn = page.locator("button, div").filter(has_text=re.compile(r"^Status:")).first
        
        if "Solved" not in status_btn.inner_text():
            status_btn.click()
            time.sleep(0.5)
            page.locator("text=Solved").first.click()
            time.sleep(0.5)
        
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception as e:
        print(f"Note: Could not set Status filter: {e}")
        page.keyboard.press("Escape")

def clean_filename(title):
    """Converts problem title into a valid .sv filename."""
    name = title.lower()
    name = name.replace(":", "_").replace("-", "_").replace(" ", "_")
    name = re.sub(r"[^a-z0-9_]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return f"{name}.sv"

def get_monaco_code(page):
    """Retrieves code directly from Monaco Editor JS runtime."""
    try:
        return page.evaluate("""() => {
            if (window.monaco && window.monaco.editor) {
                const models = window.monaco.editor.getModels();
                if (models.length > 0) {
                    return models[0].getValue();
                }
            }
            return "";
        }""")
    except Exception:
        return ""

def sync_solutions():
    auth = Auth.Token(GITHUB_TOKEN)
    gh = Github(auth=auth)
    user = gh.get_user()
    
    try:
        repo = user.get_repo(REPO_NAME)
    except GithubException:
        repo = user.create_repo(REPO_NAME, description="My RTLHub Solutions")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir="./rtlhub_session",
            headless=False,
            no_viewport=True,
            args=[
                "--start-maximized",
                "--hide-crash-restore-bubble",
                "--disable-session-crashed-bubble",
                "--disable-infobars",
                "--no-first-run",
                "--no-default-browser-check"
            ]
        )
        
        page = context.pages[0] if context.pages else context.new_page()

        # Handle dialogs automatically ("Load last passing solution?")
        def handle_dialog(dialog):
            print(f" -> Auto-accepting dialog: '{dialog.message[:35]}...'")
            dialog.accept()

        page.on("dialog", handle_dialog)

        print("Navigating to RTLHub problems page...")
        page.goto("https://rtlhub.com/problems", wait_until="networkidle")
        time.sleep(2)

        if "login" in page.url:
            print("\n[!] Session expired. Please run `python3 login_once.py` first.")
            context.close()
            return

        print("Filtering by Status: Solved...")
        apply_solved_filter(page)

        # Extract solved problem titles
        card_locators = page.locator("div").filter(has_text=re.compile(r"Beginner|Easy|Medium|Hard")).all()
        
        solved_titles = []
        ignore_list = ["Difficulty: All", "Status: Solved", "Status: All", "RTLHub", "Beginner", "Easy", "Medium", "Hard"]

        for card in card_locators:
            text = card.inner_text().strip()
            lines = [line.strip() for line in text.split("\n") if line.strip()]
            if lines:
                title = lines[0]
                if title not in solved_titles and title not in ignore_list:
                    solved_titles.append(title)

        print(f"\nIdentified {len(solved_titles)} solved problems to sync.")

        for title in solved_titles:
            print(f"\n--- Processing: {title} ---")
            
            if "problems" not in page.url:
                page.goto("https://rtlhub.com/problems", wait_until="networkidle")
                time.sleep(1)
                apply_solved_filter(page)

            filename = clean_filename(title)
            file_path = f"solutions/{filename}"

            # Open card
            try:
                card_to_click = page.locator("div").filter(has_text=re.compile(rf"^{re.escape(title)}$", re.IGNORECASE)).first
                if card_to_click.count() == 0:
                    card_to_click = page.get_by_text(title, exact=True).first
                
                card_to_click.click()
                page.wait_for_url("**/problem/**", timeout=7000)
            except Exception as e:
                print(f"Could not open card '{title}': {e}")
                continue

            time.sleep(2)  # Wait for page layout

            # Click "Load your last passing solution" button
            try:
                load_btn = page.locator("[title*='last passing solution'], [aria-label*='last passing solution']").first
                if load_btn.count() > 0 and load_btn.is_visible():
                    print(" -> Clicking 'Load last passing solution'...")
                    load_btn.click()
                else:
                    page.locator("button").filter(has=page.locator("svg")).nth(1).click()
            except Exception as e:
                print(f" -> Could not click load solution button: {e}")

            # Poll Monaco Editor until actual solution code is populated
            code_text = ""
            for _ in range(10):
                code_text = get_monaco_code(page)
                if code_text and len(code_text.strip()) > 15:
                    break
                time.sleep(0.5)

            clean_code = code_text.strip()
            if not clean_code or len(clean_code) <= 10:
                print(f"[!] Skipping {title}: Could not fetch valid solution code.")
                continue

            # Check existing content on GitHub to avoid redundant commits
            try:
                existing_file = repo.get_contents(file_path)
                existing_content = existing_file.decoded_content.decode("utf-8").strip()

                # Normalize line endings (\r\n vs \n) for accurate comparison
                existing_normalized = existing_content.replace("\r\n", "\n")
                new_normalized = clean_code.replace("\r\n", "\n")

                if existing_normalized == new_normalized:
                    print(f" -> File '{file_path}' is up to date. Skipping commit.")
                    continue

                # File exists but content changed -> Update it
                repo.update_file(
                    path=file_path,
                    message=f"Update RTLHub solution: {title}",
                    content=clean_code,
                    sha=existing_file.sha
                )
                print(f" -> Updated {file_path} on GitHub.")

            except GithubException:
                # File does not exist yet -> Create it
                repo.create_file(
                    path=file_path,
                    message=f"Add RTLHub solution: {title}",
                    content=clean_code
                )
                print(f" -> Added {file_path} to GitHub.")

        context.close()
        print("\nSync completed successfully!")

if __name__ == "__main__":
    sync_solutions()
