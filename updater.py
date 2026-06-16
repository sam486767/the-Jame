import os
import subprocess
import sys
import json
import time
import shutil
from pathlib import Path
import requests

# =========================
# CONFIG
# =========================
GITHUB_USER = "sam486767"
GITHUB_REPO = "the-Jame"
GITHUB_BRANCH = "main"

BASE_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}"
VERSION_URL = f"{BASE_URL}/version.json"

# Added updater.py here so that self-patching works without throwing FileNotFoundError
FILES = {
    "game.py": f"{BASE_URL}/game.py",
    "updater.py": f"{BASE_URL}/updater.py",
    "version.json": f"{BASE_URL}/version.json",
}

VERSION_FILE = Path("version.json")
TEMP_DIR = Path("temp_update")


# =========================
# STATE
# =========================
shutdown_callback = None


# =========================
# CORE FUNCTIONS
# =========================
def load_local_versions():
    if not VERSION_FILE.exists():
        return {
            "game_version": "0.0.0",
            "updater_version": "0.0.0"
        }

    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "game_version" not in data:
                data["game_version"] = "0.0.0"
            if "updater_version" not in data:
                data["updater_version"] = "0.0.0"
            return data
    except Exception:
        return {
            "game_version": "0.0.0",
            "updater_version": "0.0.0"
        }


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
        print(f"[Updater] Downloading {filename}...")
        download_file(url, TEMP_DIR / filename)


def replace_game_files():
    print("[Updater] Updating game files...")
    if (TEMP_DIR / "game.py").exists():
        shutil.copy2(TEMP_DIR / "game.py", "game.py")
    if (TEMP_DIR / "version.json").exists():
        shutil.copy2(TEMP_DIR / "version.json", "version.json")


def launch_game():
    print("[Updater] Launching game...")
    subprocess.Popen([sys.executable, "game.py"])


def cleanup():
    if TEMP_DIR.exists():
        shutil.rmtree(TEMP_DIR)


# =========================
# PATCHER
# =========================
def create_patcher():
    patcher_code = r'''import time
import shutil
import subprocess
import sys
from pathlib import Path

print("[Patcher] Waiting for file handles to release...")
time.sleep(2)

temp = Path("temp_update")
if temp.exists():
    if (temp / "updater.py").exists():
        shutil.copy2(temp / "updater.py", "updater.py")
    if (temp / "version.json").exists():
        shutil.copy2(temp / "version.json", "version.json")

    shutil.rmtree(temp)

print("[Patcher] Restarting updater...")
subprocess.Popen([sys.executable, "updater.py"])
'''

    with open("patcher.py", "w", encoding="utf-8") as f:
        f.write(patcher_code)


def run_patcher():
    subprocess.Popen([sys.executable, "patcher.py"])
    sys.exit()


# =========================
# PUBLIC ENTRY FOR GAME.PY (BACKGROUND THREAD LOOP)
# =========================
def run_updater(on_update_detected):
    global shutdown_callback
    shutdown_callback = on_update_detected

    print("[Updater] Background monitor thread started.")

    while True:
        try:
            local = load_local_versions()
            remote = get_remote_versions()

            game_update = local.get("game_version", "0.0.0") != remote.get("game_version", "0.0.0")
            updater_update = local.get("updater_version", "0.0.0") != remote.get("updater_version", "0.0.0")

            if game_update or updater_update:
                print("[Updater] Update found in background thread!")

                # Signal the game to shutdown its Tkinter loop safely
                if shutdown_callback:
                    shutdown_callback()
                
                # Give the main game window thread a brief 2-second window to close gracefully
                time.sleep(2)

                download_updates()

                if game_update:
                    replace_game_files()

                if updater_update:
                    print("[Updater] Self-update required. Handing off to patcher...")
                    create_patcher()
                    run_patcher()
                else:
                    print("[Updater] Update complete. Game assets updated for next run.")
                    cleanup()
                    break

        except Exception as e:
            print("[Updater] Background thread error:", e)

        time.sleep(300)  # Check every 5 minutes


# =========================
# MAIN ENTRY (WHEN RUN DIRECTLY AS A LAUNCHER)
# =========================
def main():
    print("[Launcher] Checking for updates...")

    try:
        local = load_local_versions()
        remote = get_remote_versions()

        game_update = local.get("game_version", "0.0.0") != remote.get("game_version", "0.0.0")
        updater_update = local.get("updater_version", "0.0.0") != remote.get("updater_version", "0.0.0")

        if game_update or updater_update:
            print("[Launcher] Update found!")
            download_updates()

            if game_update:
                replace_game_files()

            if updater_update:
                print("[Launcher] Updater needs updating...")
                create_patcher()
                run_patcher()
            else:
                print("[Launcher] Update complete.")
        else:
            print("[Launcher] Already up to date.")

    except Exception as e:
        print("[Launcher] Updater error:", e)

    cleanup()
    launch_game()


if __name__ == "__main__":
    main()# =========================
def load_local_versions():
    if not VERSION_FILE.exists():
        return {"game_version": "0.0.0"}

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


def download_update():
    TEMP_DIR.mkdir(exist_ok=True)

    for name, url in FILES.items():
        print(f"[Updater] downloading {name}")
        download_file(url, TEMP_DIR / name)


def apply_update():
    print("[Updater] applying update...")

    shutil.copy2(TEMP_DIR / "game.py", "game.py")
    shutil.copy2(TEMP_DIR / "version.json", "version.json")

    shutil.rmtree(TEMP_DIR)


# =========================
# PUBLIC ENTRY
# =========================
def run_updater(on_update_detected):
    global shutdown_callback
    shutdown_callback = on_update_detected

    print("[Updater] started")

    while True:
        try:
            local = load_local_versions()
            remote = get_remote_versions()

            if local["game_version"] != remote["game_version"]:
                print("[Updater] update found!")

                # 🔥 signal game to stop
                shutdown_callback()

                download_update()
                apply_update()

                print("[Updater] update complete")

                break

        except Exception as e:
            print("[Updater] error:", e)

        time.sleep(300)  # 5 minutesdef load_local_versions():
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
