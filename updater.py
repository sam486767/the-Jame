import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path

import requests

# =========================
# CONFIG
# =========================
GITHUB_USER = "YOUR_USERNAME"
GITHUB_REPO = "YOUR_REPO"
GITHUB_BRANCH = "main"

BASE_URL = (
    f"https://raw.githubusercontent.com/"
    f"{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
)

VERSION_URL = f"{BASE_URL}/version.json"

FILES = {
    "game.py": f"{BASE_URL}/game.py",
    "updater.py": f"{BASE_URL}/updater.py",
    "version.json": f"{BASE_URL}/version.json",
}

VERSION_FILE = Path("version.json")
TEMP_DIR = Path("temp_update")

# =========================
# HELPERS
# =========================
def load_local_versions():
    if not VERSION_FILE.exists():
        return {
            "game_version": "0.0.0",
            "updater_version": "0.0.0"
        }

    with open(VERSION_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_remote_versions():
    r = requests.get(VERSION_URL)
    r.raise_for_status()
    return r.json()


def download_file(url, destination):
    r = requests.get(url)
    r.raise_for_status()

    with open(destination, "wb") as f:
        f.write(r.content)


def download_updates():
    TEMP_DIR.mkdir(exist_ok=True)

    for filename, url in FILES.items():
        print(f"Downloading {filename}...")
        download_file(url, TEMP_DIR / filename)


def replace_game_files():
    print("Updating game files...")

    shutil.copy2(TEMP_DIR / "game.py", "game.py")
    shutil.copy2(TEMP_DIR / "version.json", "version.json")


def launch_game():
    print("Launching game...")
    subprocess.Popen([sys.executable, "game.py"])


def cleanup():
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)


# =========================
# PATCHER
# =========================
def create_patcher():
    patcher_code = r'''
import time
import shutil
import subprocess
import sys
from pathlib import Path

time.sleep(2)

temp = Path("temp_update")
if temp.exists():
    shutil.copy2(temp / "updater.py", "updater.py")
    shutil.copy2(temp / "version.json", "version.json")

    shutil.rmtree(temp)

subprocess.Popen([sys.executable, "updater.py"])
'''

    with open("patcher.py", "w", encoding="utf-8") as f:
        f.write(patcher_code)


def run_patcher():
    subprocess.Popen([sys.executable, "patcher.py"])
    sys.exit()


# =========================
# MAIN
# =========================
def main():
    print("Checking for updates...")

    try:
        local = load_local_versions()
        remote = get_remote_versions()

        game_update = (
            local["game_version"] != remote["game_version"]
        )

        updater_update = (
            local["updater_version"] != remote["updater_version"]
        )

        if game_update or updater_update:
            print("Update found!")
            download_updates()

            if game_update:
                replace_game_files()

            if updater_update:
                print("Updater needs updating...")
                create_patcher()
                run_patcher()

        else:
            print("Already up to date.")

    except Exception as e:
        print("Updater error:", e)

    cleanup()
    launch_game()


if __name__ == "__main__":
    main()
