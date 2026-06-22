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

FILES = {
    "game.py": f"{BASE_URL}/game.py",
    "updater.py": f"{BASE_URL}/updater.py",
    "version.json": f"{BASE_URL}/version.json",
    "vault.json": f"{BASE_URL}/vault.json",
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
    # Cache Buster: Append a unique timestamp so GitHub cannot serve a cached file
    cache_buster_url = f"{VERSION_URL}?t={int(time.time())}"
    r = requests.get(cache_buster_url)
    r.raise_for_status()
    return r.json()


def download_file(url, destination):
    # Cache Buster applied to file downloads to guarantee the freshest code gets pulled
    cache_buster_url = f"{url}?t={int(time.time())}"
    r = requests.get(cache_buster_url)
    r.raise_for_status()

    with open(destination, "wb") as f:
        f.write(r.content)


def download_updates():
    TEMP_DIR.mkdir(exist_ok=True)

    for filename, url in FILES.items():
        print(f"[Updater] Downloading {filename}...")
        try:
            download_file(url, TEMP_DIR / filename)
        except Exception as e:
            print(f"[Updater] Warning: Could not download {filename}: {e}")


def replace_game_files():
    print("[Updater] Updating game files...")
    if (TEMP_DIR / "game.py").exists():
        shutil.copy2(TEMP_DIR / "game.py", "game.py")
    if (TEMP_DIR / "version.json").exists():
        shutil.copy2(TEMP_DIR / "version.json", "version.json")
    if (TEMP_DIR / "vault.json").exists():
        shutil.copy2(TEMP_DIR / "vault.json", "vault.json")


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
    if (temp / "vault.json").exists():
        shutil.copy2(temp / "vault.json", "vault.json")

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

            game_update = str(local.get("game_version", "0.0.0")).strip() != str(remote.get("game_version", "0.0.0")).strip()
            updater_update = str(local.get("updater_version", "0.0.0")).strip() != str(remote.get("updater_version", "0.0.0")).strip()

            if game_update or updater_update:
                print("[Updater] Update found in background thread!")

                if shutdown_callback:
                    shutdown_callback()
                
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

        time.sleep(300)


# =========================
# MAIN ENTRY (WHEN RUN DIRECTLY AS A LAUNCHER)
# =========================
def main():
    print("[Launcher] Checking for updates...")

    try:
        local = load_local_versions()
        remote = get_remote_versions()

        game_update = str(local.get("game_version", "0.0.0")).strip() != str(remote.get("game_version", "0.0.0")).strip()
        updater_update = str(local.get("updater_version", "0.0.0")).strip() != str(remote.get("updater_version", "0.0.0")).strip()

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
    main()
