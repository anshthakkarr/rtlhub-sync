import os
import time
import re
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from github import Github, Auth, GithubException

load_dotenv()
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise ValueError("[!] GITHUB_TOKEN missing! Please check your .env file.")

REPO_NAME = "rtlhub-solutions"

def apply_solved_filter(page):
    """Clicks the Status dropdown, selects 'Solved', and guarantees overlay dismissal."""
    try:
        status_btn = page.locator("button, div").filter(has_text=re.compile(r"^Status:")).first

        if status_btn.count() > 0:
            current_text = status_btn.inner_text()
            if "Solved" not in current_text:
                status_btn.click()
                # time.sleep(0.5)
                
                solved_option = page.get_by_text("Solved", exact=True).first
                if solved_option.is_visible():
                    solved_option.click()
                    # time.sleep(0.5)

        # Dismiss dropdown overlay: press Escape AND click neutral screen coordinates (10, 10)
        page.keyboard.press("Escape")
        # time.sleep(0.2)
        page.mouse.click(10, 10)
        # time.sleep(0.5)
    except Exception as e:
        print(f"Note: Could not set Status filter: {e}")
        page.keyboard.press("Escape")
        page.mouse.click(10, 10)

def clean_slug(text):
    """Converts problem titles or filenames into clean, standard identifiers."""
    name = text.lower().strip()
    name = name.replace(":", "_").replace("-", "_").replace(" ", "_")
    name = re.sub(r"[^a-z0-9_.]", "", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name

def get_monaco_code(page, tab_name=""):
    """Retrieves code matching the target tab/module (.sv or .v) from Monaco Editor instances."""
    try:
        return page.evaluate("""(targetTab) => {
            if (!window.monaco || !window.monaco.editor) return "";
            
            const editors = window.monaco.editor.getEditors();
            if (editors.length === 0) return "";

            // Clean tab name to match Verilog/SV module identifier (e.g. "my_module.v" -> "my_module")
            const cleanTarget = targetTab ? targetTab.replace(/\\.(sv|v)$/i, "").toLowerCase().trim() : "";

            // Try matching code that contains "module <cleanTarget>"
            if (cleanTarget) {
                for (const ed of editors) {
                    const isReadOnly = ed.getRawOptions ? ed.getRawOptions().readOnly : false;
                    if (!isReadOnly && ed.getModel()) {
                        const code = ed.getModel().getValue();
                        if (code.toLowerCase().includes("module " + cleanTarget)) {
                            return code;
                        }
                    }
                }

                // Try matching models directly
                const models = window.monaco.editor.getModels();
                for (const mod of models) {
                    const code = mod.getValue();
                    if (code.toLowerCase().includes("module " + cleanTarget)) {
                        return code;
                    }
                }
            }

            // Fallback: return the first editable editor with content
            for (const ed of editors) {
                const isReadOnly = ed.getRawOptions ? ed.getRawOptions().readOnly : false;
                if (!isReadOnly && ed.getModel()) {
                    const code = ed.getModel().getValue();
                    if (code.trim().length > 10) return code;
                }
            }

            return "";
        }""", tab_name)
    except Exception as e:
        print(f"   -> Error reading Monaco code: {e}")
        return ""

def click_code_tab(page, tab_name):
    """Finds and clicks an editor tab in the right-side Code panel."""
    try:
        elements = page.get_by_text(tab_name).all()
        for elem in reversed(elements):
            if not elem.is_visible():
                continue

            is_ref = elem.evaluate("""el => {
                let curr = el;
                while (curr && curr !== document.body) {
                    if (curr.innerText && curr.innerText.includes('Reference Files') && !curr.innerText.includes('Code')) {
                        return true;
                    }
                    curr = curr.parentElement;
                }
                return false;
            }""")

            if not is_ref:
                elem.click(force=True)
                time.sleep(0.2)
                return True
    except Exception as e:
        print(f"   -> Could not click tab '{tab_name}': {e}")
    return False

def sync_solutions():
    auth = Auth.Token(GITHUB_TOKEN)
    gh = Github(auth=auth)
    user = gh.get_user()
    
    try:
        repo = user.get_repo(REPO_NAME)
    except GithubException:
        repo = user.create_repo(REPO_NAME, description="My RTLHub Solutions")

    # Track commit stats
    committed_count = 0
    skipped_count = 0

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

        def handle_dialog(dialog):
            print(f"    -> Auto-accepting dialog: '{dialog.message[:35]}...'")
            dialog.accept()

        page.on("dialog", handle_dialog)

        print("Navigating to RTLHub problems page...")
        page.goto("https://rtlhub.com/problems", wait_until="networkidle")
        time.sleep(0.2)

        if "login" in page.url:
            print("\n[!] Session expired. Please run `python3 login_once.py` first.")
            context.close()
            return

        print("Filtering by Status: Solved...")
        apply_solved_filter(page)

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
                time.sleep(0.2)
                apply_solved_filter(page)

            try:
                card_to_click = page.locator("div").filter(has_text=re.compile(rf"^{re.escape(title)}$", re.IGNORECASE)).first
                if card_to_click.count() == 0:
                    card_to_click = page.get_by_text(title, exact=True).first
                
                card_to_click.click(force=True)
                page.wait_for_url("**/problem/**", timeout=7000)
            except Exception as e:
                print(f"Could not open card '{title}': {e}")
                continue

            time.sleep(0.2)

            # Detect editor tabs (.sv or .v files) while filtering OUT tabs inside the "Reference Files" panel
            tab_elements = page.locator("button, div, span").filter(has_text=re.compile(r"\.(sv|v)", re.IGNORECASE)).all()
            
            tabs = []
            for elem in tab_elements:
                txt = elem.inner_text().strip()
                match = re.search(r"([a-zA-Z0-9_]+\.(?:sv|v))", txt, re.IGNORECASE)
                if not match:
                    continue
                
                clean_filename = match.group(1)

                is_ref_tab = elem.evaluate("""el => {
                    let curr = el;
                    while (curr && curr !== document.body) {
                        if (curr.innerText && curr.innerText.includes('Reference Files') && !curr.innerText.includes('Code')) {
                            return true;
                        }
                        curr = curr.parentElement;
                    }
                    return false;
                }""")

                if not is_ref_tab and clean_filename not in tabs:
                    tabs.append(clean_filename)

            folder_slug = clean_slug(title)
            is_multi_file = len(tabs) > 1

            if is_multi_file:
                print(f" -> Multi-file problem detected ({len(tabs)} files). Target folder: solutions/{folder_slug}/")
            else:
                tabs = [tabs[0]] if tabs else [f"{folder_slug}.sv"]

            for tab_name in tabs:
                clean_tab_filename = clean_slug(tab_name)
                
                # Ensure appropriate Verilog / SystemVerilog file extension is kept or appended
                if not (clean_tab_filename.endswith(".sv") or clean_tab_filename.endswith(".v")):
                    clean_tab_filename += ".sv"

                if is_multi_file:
                    print(f"  [Tab: {tab_name}]")
                    click_code_tab(page, tab_name)

                # Click "Load last passing solution" button
                try:
                    load_btn = page.locator("[title*='last passing solution'], [aria-label*='last passing solution']").first
                    if load_btn.count() > 0 and load_btn.is_visible():
                        load_btn.click(force=True)
                    else:
                        page.locator("button").filter(has=page.locator("svg")).nth(1).click(force=True)
                    
                    time.sleep(0.2)
                except Exception as e:
                    print(f"   -> Could not click load solution button: {e}")

                # Extract code matching the specific tab filename
                code_text = ""
                for _ in range(10):
                    code_text = get_monaco_code(page, tab_name)
                    if code_text and len(code_text.strip()) > 15:
                        break
                    time.sleep(0.2)

                clean_code = code_text.strip()

                if not clean_code or len(clean_code) <= 10:
                    print(f"   [!] Skipping {tab_name}: Code empty or unreadable.")
                    skipped_count += 1
                    continue

                if is_multi_file:
                    file_path = f"solutions/{folder_slug}/{clean_tab_filename}"
                else:
                    file_path = f"solutions/{folder_slug}{'.v' if clean_tab_filename.endswith('.v') else '.sv'}"

                # Content comparison check before committing
                try:
                    existing_file = repo.get_contents(file_path)
                    existing_content = existing_file.decoded_content.decode("utf-8").strip()

                    if existing_content.replace("\r\n", "\n") == clean_code.replace("\r\n", "\n"):
                        print(f"   -> Path '{file_path}' is up to date. Skipping commit.")
                        skipped_count += 1
                        continue

                    repo.update_file(
                        path=file_path,
                        message=f"Update RTLHub solution: {title} ({tab_name})",
                        content=clean_code,
                        sha=existing_file.sha
                    )
                    print(f"   -> Updated {file_path} on GitHub.")
                    committed_count += 1

                except GithubException:
                    repo.create_file(
                        path=file_path,
                        message=f"Add RTLHub solution: {title} ({tab_name})",
                        content=clean_code
                    )
                    print(f"   -> Created {file_path} on GitHub.")
                    committed_count += 1

        context.close()
        print("\nSync completed successfully!")
        print(f"Summary: {committed_count} files committed, {skipped_count} files skipped.")

if __name__ == "__main__":
    sync_solutions()
