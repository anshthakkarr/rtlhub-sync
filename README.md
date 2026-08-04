# rtlhub-sync

An automated Python pipeline that extracts solved SystemVerilog problems from RTLHub and synchronizes them to a target GitHub repository `rtlhub-solutions`.

## Tech Stack
* **Playwright:** Handles headless browser automation, tab navigation, dialog auto-acceptance, and runtime JavaScript injection into the Monaco Editor.
* **PyGithub:** Interfaces with the GitHub REST API to perform idempotent updates and manage directory structures.
* **Chromium (Persistent Context):** Stores authenticated cookies and session state in a local directory to bypass repeated logins.

## Installation

```
pip install -r requirements.txt
playwright install chromium
```

## Script Execution

1. **Establish Session (one-time).** Launches the browser to log in manually. The session profile is saved locally to `./rtlhub_session`.
   ```
   python3 src/login_once.py
   ```

2. **Run Sync.** Executes the main automated extraction and pushes updated solutions to GitHub.
   ```
   python3 src/sync_rtlhub.py
   ```


