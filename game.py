import threading
import random
import sys
import time
import json
import os
import tkinter as tk
from tkinter import messagebox, simpledialog
from datetime import datetime, timezone, timedelta
import requests
import updater

# =====================================================================
# GLOBAL CONFIGURATIONS & GAME PARAMETERS
# =====================================================================
MUTATION_WEIGHTS = {
    "ENABLE_GUNS": 10, "DISABLE_GUNS": 10, "DOUBLE_DAMAGE": 8, "HALF_DAMAGE": 8,
    "ENABLE_TRIVIA": 10, "ADD_REGEN": 10, "SUDDEN_DEATH": 2,
    "INCREASE_PLAYER_HP": 8, "INCREASE_CPU_HP": 8, "DECREASE_PLAYER_HP": 8, "DECREASE_CPU_HP": 8,
    "SWAP_HP": 2, "STEAL_HP": 4, "HP_EQUALISE": 3,
    "INCREASE_BASE_DAMAGE": 10, "DECREASE_BASE_DAMAGE": 10, "ENABLE_SHIELDS": 10,
    "GLOBAL_DAMAGE_BOOST": 8, "GLOBAL_DAMAGE_REDUCE": 8, "CRIT_BOOST": 8, "CRIT_REDUCE": 8,
    "REVERSE_DAMAGE": 4, "RANDOM_DAMAGE_SPIKE": 5, "LOW_HP_WIN": 1, "HIGH_HP_WIN": 1,
    "BOMB_INSTALL": 5, "BOMB_ACCELERATE": 5, "BOMB_SLOW": 5, "ENABLE_RPS": 4,
    "INFUSE_POISON": 8, "INFUSE_BURN": 8, "INFUSE_SLEEP": 6, "INFUSE_PARALYZE": 6, "INFUSE_FREEZE": 5,
    "INFUSE_ACID": 7, "ENABLE_50_50": 2, "DEFUSE_EFFECTS": 3,
    "PENALTY_SHOOTOUT_LTM": 3, "RED_CARD_LTM": 2,
    
    # BONUS MUTATIONS
    "ARMOR_PIERCE": 7,
    "LIFE_STEAL": 6,
    "DAMAGE_REFLECT": 5,
    "TIME_WARP": 4,
    "POISON_ALL": 6,
    "HARDCORE_MODE": 3,
}

SEASON_PASS_REWARDS = [
    {"tier": 1, "xp_required": 100, "id": "OVERCHARGE_LTM", "desc": "Instantly shifts Base Damage significantly."},
    {"tier": 2, "xp_required": 250, "id": "NANITE_SHIELD_LTM", "desc": "Generates persistent mechanical defenses."},
    {"tier": 3, "xp_required": 500, "id": "VAMPIRE_FANG_LTM", "desc": "Drains HP from your opponent directly."},
    {"tier": 4, "xp_required": 800, "id": "ECLIPSE_LTM", "desc": "Blinds central UI processing systems."},
    {"tier": 5, "xp_required": 1200, "id": "SINGULARITY_LTM", "desc": "Detonates immediate catastrophic state shifts."}
]

TRIVIA = [
    {"q": "What is 2 + 2?", "a": "4"},
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "What planet do we live on?", "a": "earth"},
    {"q": "What is 10 / 2?", "a": "5"},
    {"q": "What colour is the sky on a clear day?", "a": "blue"}
]

# =====================================================================
# CENTRALISED SYSTEM APPLICATION ENGINE
# =====================================================================
class MutationArenaApp:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("MUTATION ARENA: CARD EDITION")
        self.root.geometry("950x750")
        self.root.configure(bg="#121212")

        # Threat Thread Signal Handling
        self.update_requested = False
        self.running = True
        
        # Operational In-Game Values
        self.bomb_timer = None
        self.mutation_turn_toggle = True
        self.processing_turn = False
        self.game_active = True 
        
        # Define Static Chrono Targets (Anchor: July 13, 2026, 12 PM UTC)
        self.season_end = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
        self.season_start = self.season_end - timedelta(days=28) # 4-week structured block
        
        # Dynamic State Setup
        self.state = {}
        self.clear_rules_dict()
        self.state.update({
            "player_hp": 150, "cpu_hp": 150, "base_damage": 10,
            "player_defense": 0, "cpu_defense": 0, "turn": 1, "player_deck": [],
            "statuses": {
                "player": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False},
                "cpu": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False}
            },
            "regen_value": 0
        })
        
        # UI Elements Cache
        self.player_panel = None
        self.cpu_panel = None
        self.p_hp_lbl = None
        self.c_hp_lbl = None
        self.turn_lbl = None
        self.global_rules_lbl = None
        self.rules_lbl = None
        self.log_box = None
        self.action_area = None
        self.draft_frame = None
        self.pass_frame = None
        self.counter_lbl = None
        self.event_banner_lbl = None

        # Profile Execution Data Layer
        self.xp_file = "xp.json"
        self.player_xp = 0
        self.load_xp_profile()

        # Vault System Sync
        self.vaulted_cards = []
        self._sync_vault()

        # Spin up Asynchronous Threading Channels safely
        threading.Thread(target=self.start_updater, daemon=True).start()
        self.check_updater_signals()

    def _sync_vault(self):
        """Synchronizes with the remote vault.json on GitHub on boot to disable specific cards."""
        try:
            url = f"{updater.BASE_URL}/vault.json?t={int(time.time())}"
            r = requests.get(url, timeout=4)
            if r.status_code == 200:
                data = r.json()
                self.vaulted_cards = data.get("vaulted", [])
                print(f"[Vault] Matrix synchronized. Vaulted cards: {self.vaulted_cards}")
            else:
                print(f"[Vault] Remote vault not found (Status {r.status_code}), proceeding with all cards unlocked.")
        except Exception as e:
            print(f"[Vault] Vault synchronization failed, proceeding with local definitions. Error: {e}")

    def get_current_event_state(self):
        """Calculates current season countdown and figures out which weekly macro 
        event window and weekend multiplier rules apply based on structural timelines.
        """
        now = datetime.now(timezone.utc)
        time_remaining = self.season_end - now
        
        if time_remaining.total_seconds() <= 0:
            return {"active": False, "multiplier": 1, "label": "Season Concluded", "cd": "0d 0h", "weekend": False}
            
        # Determine current structural week index inside the 4-week window
        days_passed = (now - self.season_start).total_seconds() / 86400
        current_week = int(days_passed // 7) + 1  # Standardizes ranges to Weeks 1, 2, 3, or 4
        
        # Assign structural baseline multipliers based on calendar matrix rows
        week_multipliers = {1: 3, 2: 2, 3: 1, 4: 10}
        week_labels = {
            1: "3X XP Launch Event",
            2: "2X XP Mid-Season Surge",
            3: "Standard Operational Phase",
            4: "10X GRAND FINALE CRASH"
        }
        
        target_mult = week_multipliers.get(current_week, 1)
        target_lbl = week_labels.get(current_week, "Standard Phase")
        
        # Identify if current execution day falls inside the explicit Weekend Target Frame (Friday 12 PM UTC - Monday 12 PM UTC)
        is_weekend = False
        current_weekday = now.weekday() # Mon=0, Tue=1 ... Fri=4, Sat=5, Sun=6
        
        # Find structural boundary timestamps for the immediate weekend
        days_until_friday = (4 - current_weekday) % 7
        if current_weekday in [4, 5, 6, 0]: # Actively processing around weekend boundaries
            if current_weekday == 0 and now.hour >= 12:
                days_until_friday = 4 # Past Monday boundary cutoff, forward trace to next Friday
            else:
                if current_weekday == 0: days_until_friday = -3
                else: days_until_friday = -(current_weekday - 4)
                
        wknd_start = datetime(now.year, now.month, now.day, 12, 0, 0, tzinfo=timezone.utc) + timedelta(days=days_until_friday)
        wknd_end = wknd_start + timedelta(days=3)
        
        if wknd_start <= now <= wknd_end:
            is_weekend = True
            
        final_multiplier = target_mult if is_weekend else 1
        
        # Build out structural string countdown data formatting
        days = time_remaining.days
        hours, remainder = divmod(time_remaining.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        countdown_str = f"{days}d {hours:02d}h {minutes:02d}m"
        
        return {
            "active": True,
            "multiplier": final_multiplier,
            "base_multiplier": target_mult,
            "label": target_lbl,
            "cd": countdown_str,
            "weekend": is_weekend,
            "wknd_start": wknd_start,
            "wknd_end": wknd_end
        }

    def get_xp_multiplier(self):
        return self.get_current_event_state()["multiplier"]

    def clear_rules_dict(self):
        self.state["rules"] = {
            "guns_enabled": False, "trivia": False, "double_damage": False, "regen": False,
            "sudden_death": False, "reverse_damage": False, "random_damage_spike": False,
            "crit_boost": False, "low_hp_win": False, "high_hp_win": False, "rps_mode": False,
            "infuse_poison": False, "infuse_burn": False, "infuse_sleep": False,
            "infuse_paralyze": False, "infuse_freeze": False, "infuse_acid": False, "fifty_fifty": False,
            "overcharge": False, "nanite_shield": False, "vampire_fang": False, "eclipse": False, "singularity": False,
            "armor_pierce": False, "life_steal": False, "damage_reflect": False, "poison_all": False
        }

    def reset_game_state(self):
        self.load_xp_profile()
        self.bomb_timer = None
        self.mutation_turn_toggle = True
        self.processing_turn = False
        self.game_active = True
        
        self.state.update({
            "player_hp": 150, "cpu_hp": 150, "base_damage": 10,
            "player_defense": 0, "cpu_defense": 0, "turn": 1,
            "statuses": {
                "player": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False},
                "cpu": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False}
            },
            "regen_value": 0
        })
        self.clear_rules_dict()

    def load_xp_profile(self):
        if os.path.exists(self.xp_file):
            try:
                with open(self.xp_file, 'r') as f:
                    data = json.load(f)
                    self.player_xp = data.get("S1_xp", 0)
            except Exception as e:
                print(f"[Engine] File error parsing JSON matrix: {e}. Resetting values.")
                self.player_xp = 0
        else:
            self.player_xp = 0  
            self.save_xp_profile()

    def save_xp_profile(self):
        try:
            with open(self.xp_file, 'w') as f:
                json.dump({"S1_xp": self.player_xp}, f, indent=4)
        except Exception as e:
            print(f"[Fatal Storage Error] Could not parse save data stream: {e}")

    def add_match_xp(self, base_reward=120):
        ev = self.get_current_event_state()
        final_reward = base_reward * ev["multiplier"]
        self.player_xp += final_reward
        self.save_xp_profile()
        
        event_tag = f" [GLOBAL {ev['multiplier']}X MULTIPLIER ACTIVE]" if ev["multiplier"] > 1 else ""
        self.game_log(f"⭐ Data vectors merged! Received +{final_reward} S1_XP{event_tag} (Total: {self.player_xp})", "victory")

    def is_reward_unlocked(self, reward_id):
        for item in SEASON_PASS_REWARDS:
            if item["id"] == reward_id:
                return self.player_xp >= item["xp_required"]
        return True

    # =====================================================================
    # THREAD-SAFE APPLICATION MANAGEMENT
    # =====================================================================
    def request_game_shutdown(self):
        self.update_requested = True

    def start_updater(self):
        updater.run_updater(self.request_game_shutdown)

    def check_updater_signals(self):
        if self.update_requested:
            self.shutdown_application()
            return
        self.root.after(500, self.check_updater_signals)

    def shutdown_application(self):
        self.game_active = False
        self.root.quit()
        try:
            self.root.destroy()
        except Exception:
            pass
        sys.exit(0)

    # =====================================================================
    # REFACTORED GRAPHICAL INTERFACE AND STYLED LOG CHANNELS
    # =====================================================================
    def init_log_tags(self):
        """Pre-allocates standard styling metrics to avoid tag memory leaking maps."""
        self.log_box.tag_config("system", foreground="#ffcc00")
        self.log_box.tag_config("combat", foreground="#ff7675")
        self.log_box.tag_config("victory", foreground="#2ecc71")
        self.log_box.tag_config("trivia", foreground="#4fc3f7")
        self.log_box.tag_config("normal", foreground="#ffffff")

    def game_log(self, message, style_tag="normal"):
        print(message)
        if self.log_box is not None and self.log_box.winfo_exists():
            try:
                self.log_box.configure(state='normal')
                self.log_box.insert(tk.END, message + "\n", style_tag)
                self.log_box.see(tk.END)
                self.log_box.configure(state='disabled')
            except Exception:
                pass

    def update_status_displays(self):
        if not self.p_hp_lbl or not self.p_hp_lbl.winfo_exists(): return
            
        self.p_hp_lbl.config(text=f"HP: {self.state['player_hp']}")
        self.c_hp_lbl.config(text=f"HP: {self.state['cpu_hp']}")
        self.turn_lbl.config(text=f"ROUND {self.state['turn']}")
        
        stats_text = f"Base Attack Value: {self.state['base_damage']}  |  Shield Capacity (P/C): {self.state['player_defense']}/{self.state['cpu_defense']}"
        if self.bomb_timer is not None:
            stats_text += f"  |  💣 BOMB COUNTDOWN: {self.bomb_timer}"
        self.global_rules_lbl.config(text=stats_text)
        
        active_rules = [k for k, v in self.state["rules"].items() if v]
        self.rules_lbl.config(text="Global Mutations: " + (", ".join(active_rules) if active_rules else "None"))

    def get_weighted_mutations(self, k):
        # Filter out vaulted cards from the pool
        population = [m for m in MUTATION_WEIGHTS.keys() if m not in self.vaulted_cards]
        for r in SEASON_PASS_REWARDS:
            if self.is_reward_unlocked(r["id"]) and r["id"] not in self.vaulted_cards:
                population.append(r["id"])

        weights = [MUTATION_WEIGHTS.get(mut, 5) for mut in population]
        chosen = []
        for _ in range(min(k, len(population))):
            c = random.choices(population, weights=weights, k=1)[0]
            idx = population.index(c)
            chosen.append(c)
            population.pop(idx)
            weights.pop(idx)
        return chosen

    def trigger_damage_cutscene(self, target, damage_dealt):
        if not self.game_active: return
        target_frame = self.player_panel if target == "player" else self.cpu_panel
        if not target_frame or not target_frame.winfo_exists(): return
        original_bg = target_frame.cget("bg")
        
        def flash(count):
            if not self.game_active or not target_frame.winfo_exists(): return
            if count <= 0:
                target_frame.config(bg=original_bg)
                return
            target_frame.config(bg="#b21c1c" if count % 2 == 0 else original_bg)
            self.root.after(60, lambda: flash(count - 1))

        def shake(step, current_x=0):
            if not self.game_active or not target_frame.winfo_exists(): return
            if step <= 0:
                target_frame.pack_configure(padx=20)
                return
            offset = random.choice([-12, 12])
            target_frame.pack_configure(padx=20 + offset)
            self.root.after(40, lambda: shake(step - 1, offset))

        popup = tk.Label(target_frame, text=f"-{damage_dealt} HP!", font=("Courier", 24, "bold"), bg="#121212", fg="#ff3333")
        popup.place(relx=0.5, rely=0.3, anchor="center")
        
        def float_up(ticks, current_y=0.3):
            if not self.game_active or not popup.winfo_exists(): return
            if ticks <= 0:
                popup.destroy()
                return
            popup.place(relx=0.5, rely=current_y - 0.02, anchor="center")
            self.root.after(50, lambda: float_up(ticks - 1, current_y - 0.02))

        flash(5)
        shake(8)
        float_up(12)

    def clear_action_space(self):
        if self.action_area and self.action_area.winfo_exists():
            for widget in self.action_area.winfo_children():
                if widget.winfo_exists(): widget.destroy()

    def get_card_design(self, mutation_key):
        display_name = mutation_key.replace("_LTM", "").replace("_", " ")
        if mutation_key.endswith("_LTM") and any(r["id"] == mutation_key for r in SEASON_PASS_REWARDS):
            if not self.is_reward_unlocked(mutation_key):
                return f"🔒 [LOCKED TIER]\n{display_name}", "#242424", "#555555", "#888888", "#242424"
            return f"🌟 {display_name}", "#1b262c", "#00d2d3", "#00d2d3", "#223a47"
        if mutation_key.endswith("_LTM"):
            return display_name, "#2c1a3a", "#e056fd", "#e056fd", "#431f5c"
        
        if mutation_key == "HARDCORE_MODE": return display_name, "#3a0000", "#ff0000", "#ff3333", "#5c0000"
        if any(kw in mutation_key for kw in ["DAMAGE", "GUNS", "CRIT", "STRIKE", "INFUSE", "PIERCE"]):
            return display_name, "#2d1414", "#ff4757", "#ff4757", "#4a1c1c"
        if any(kw in mutation_key for kw in ["HP", "REGEN", "EQUALISE", "SHIELDS", "STEAL", "LIFE"]):
            return display_name, "#112415", "#2ed573", "#2ed573", "#1b3d22"
        if any(kw in mutation_key for kw in ["BOMB", "50_50", "RPS", "SWAP", "REVERSE", "REFLECT", "WARP", "POISON_ALL"]):
            return display_name, "#26210f", "#ffa502", "#ffa502", "#403714"
        return display_name, "#1e222b", "#70a1ff", "#70a1ff", "#2f3640"

    def create_graphic_card(self, parent, title, command_callback):
        display_name, bg_color, border_color, text_color, hover_bg = self.get_card_design(title)
        card = tk.Frame(parent, bg=bg_color, highlightbackground=border_color, highlightthickness=2, width=160, height=200)
        card.pack_propagate(False)
        
        lbl = tk.Label(card, text=display_name, font=("Courier", 10, "bold"), fg=text_color, bg=bg_color, wraplength=140)
        lbl.pack(expand=True, fill="both", padx=10, pady=10)
        
        is_locked = "🔒" in display_name
        def trigger_click(e): 
            if not is_locked: command_callback(title)
            else: messagebox.showwarning("Access Vector Restricted", "Acquire additional S1_XP profiles to unlock.")
                
        card.bind("<Button-1>", trigger_click)
        lbl.bind("<Button-1>", trigger_click)
        if not is_locked:
            card.bind("<Enter>", lambda e: card.config(bg=hover_bg))
            card.bind("<Leave>", lambda e: card.config(bg=bg_color))
            lbl.bind("<Enter>", lambda e: [card.config(bg=hover_bg), lbl.config(bg=hover_bg)])
            lbl.bind("<Leave>", lambda e: [card.config(bg=bg_color), lbl.config(bg=bg_color)])
        return card

    # =====================================================================
    # COMBAT AND GAME TERMINATION CHECK LOOPS
    # =====================================================================
    def check_game_over(self):
        if not self.game_active: return True
        p_dead, c_dead = self.state["player_hp"] <= 0, self.state["cpu_hp"] <= 0

        if p_dead or c_dead:
            self.game_active = False  
            self.update_status_displays()
                
            msg = f"Final Standings:\nPlayer HP: {self.state['player_hp']} | CPU HP: {self.state['cpu_hp']}\n\n"
            p_won = False
            if self.state["rules"]["low_hp_win"]:
                if self.state["player_hp"] < self.state["cpu_hp"]: p_won = True
            elif self.state["rules"]["high_hp_win"]:
                if self.state["player_hp"] > self.state["cpu_hp"]: p_won = True
            elif c_dead and not p_dead: p_won = True

            if p_won:
                msg += "PLAYER WINS! Synchronizing data vectors...\n\n"
                self.add_match_xp(10)  
            else:
                msg += "MATCH CONCLUDED.\n\n"
                self.add_match_xp(5)   
                
            replay = messagebox.askyesno("⚡ ARENA TERMINATION ⚡", msg + "Draft a new deck and play another match?")
            if replay:
                for widget in self.root.winfo_children():
                    if widget.winfo_exists(): widget.destroy()
                self.reset_game_state()
                self.execute_deck_draft_gui()
            else:
                self.shutdown_application()
            return True
        return False

    def try_trivia(self, attacker, complete_callback):
        if not self.game_active: return
        if not self.state["rules"]["trivia"] or random.random() > 0.25:
            complete_callback("pass")
            return

        q = random.choice(TRIVIA)
        self.game_log(f"❓ TRIVIA OVERRIDE ISSUED FOR {attacker.upper()}!", "trivia")
        
        if attacker == "cpu":
            ans = q["a"] if random.random() > 0.5 else "wrong_answer"
            self.game_log(f"CPU selected: {ans}")
            complete_callback("correct" if ans == q["a"] else "wrong")
        else:
            user_ans = simpledialog.askstring("TRIVIA TIME!", f"Question: {q['q']}")
            if user_ans is None:
                self.game_log("✖ Player skipped trivia and forfeit the challenge turn sequence.", "trivia")
                complete_callback("forfeit")
                return
            user_ans = user_ans.strip().lower()
            if user_ans == q["a"]:
                self.game_log("✔ Player Answer Correct!", "victory")
                complete_callback("correct")
            else:
                self.game_log("✖ Player Answer Incorrect!", "combat")
                complete_callback("wrong")

    def apply_status_roll(self, defender):
        if not self.game_active: return
        chance = 0.3
        if self.state["rules"]["infuse_poison"] and random.random() < chance:
            self.state["statuses"][defender]["poison"] += 3
            self.game_log(f"🍄 {defender.upper()} was Poisoned for 3 turns!")
        if self.state["rules"]["infuse_burn"] and random.random() < chance:
            self.state["statuses"][defender]["burn"] += 3
            self.game_log(f"🔥 {defender.upper()} was Burned for 3 turns!")
        if self.state["rules"]["infuse_sleep"] and random.random() < chance:
            self.state["statuses"][defender]["sleep"] = random.randint(1, 2)
            self.game_log(f"💤 {defender.upper()} fell asleep!")
        if self.state["rules"]["infuse_paralyze"] and random.random() < chance:
            self.state["statuses"][defender]["paralyze"] = True
            self.game_log(f"⚡ {defender.upper()} is Paralyzed!")
        if self.state["rules"]["infuse_freeze"] and random.random() < chance:
            self.state["statuses"][defender]["freeze"] = True
            self.game_log(f"🧊 {defender.upper()} was Frozen solid!")
        if self.state["rules"]["infuse_acid"] and random.random() < chance:
            self.state["statuses"][defender]["poison"] += 1
            self.game_log(f"🧪 {defender.upper()} hit with Acid! (+1 turn Poison)")

    def check_can_act(self, actor):
        if not self.game_active: return False
        s = self.state["statuses"][actor]
        if s["sleep"] > 0:
            self.game_log(f"💤 {actor.upper()} is fast asleep...")
            s["sleep"] -= 1
            return False
        if s["freeze"]:
            if random.random() < 0.25:
                self.game_log(f"🧊✨ {actor.upper()} thawed out!")
                s["freeze"] = False
            else:
                self.game_log(f"🧊 {actor.upper()} is frozen solid!")
                return False
        if s["paralyze"] and random.random() < 0.25:
            self.game_log(f"⚡ {actor.upper()} is fully paralyzed and skips action!")
            return False
        return True

    def play_penalty_shootout(self, attacker, defender):
        if not self.game_active: return
        self.game_log(f"\n⚽ {attacker.upper()} IS TAKING A PENALTY KICK!", "system")
        directions = ["left", "center", "right"]
        
        if attacker == "player":
            strike = simpledialog.askstring("PENALTY KICK!", "Where do you shoot? (left/center/right):")
            if strike: strike = strike.strip().lower()
            while strike not in directions: 
                strike = simpledialog.askstring("INVALID DIRECTION", "Choose left, center, or right:")
                if strike: strike = strike.strip().lower()
            gk_save = random.choice(directions)
        else:
            strike = random.choice(directions)
            self.game_log("🤖 CPU is preparing to shoot...")
            gk_save = simpledialog.askstring("PENALTY SAVE!", "Which way do you dive to save? (left/center/right):")
            if gk_save: gk_save = gk_save.strip().lower()
            while gk_save not in directions: 
                gk_save = simpledialog.askstring("INVALID DIRECTION", "Choose left, center, or right:")
                if gk_save: gk_save = gk_save.strip().lower()

        self.game_log(f"👟 {attacker.upper()} shoots {strike.upper()}!")
        self.game_log(f"🧤 {defender.upper()} dives {gk_save.upper()}!")
        
        if strike == gk_save:
            self.game_log(f"❌ GREAT SAVE! {defender.upper()} blocked the shot! Counter-attack dealing 10 damage to {attacker.upper()}!", "combat")
            self.state[f"{attacker}_hp"] -= 10
            if self.check_game_over(): return
            self.trigger_damage_cutscene(attacker, 10)
        else:
            goal_damage = max(35, self.state["base_damage"] * 6)
            self.game_log(f"⚽ GOAL!!! {attacker.upper()} completely fooled the keeper and scores {goal_damage} damage!", "victory")
            self.state[f"{defender}_hp"] -= goal_damage
            if self.check_game_over(): return
            self.trigger_damage_cutscene(defender, goal_damage)
            
        self.update_status_displays()

    # =====================================================================
    # REFACTORED WORKER COMBAT SYSTEM PIPELINE
    # =====================================================================
    def execute_strike(self, attacker, defender, trivia_result):
        if not self.game_active: return
        if trivia_result == "forfeit":
            self.game_log(f"🛡️ Turn skipped due to forfeit protocols.")
            return

        if self.state["rules"]["fifty_fifty"]:
            self.game_log("\n🎲 50/50 ACTIVE — PURGING ALL COIN FLIPS", "combat")
            winner = random.choice(["player", "cpu"])
            self.state["cpu" if winner == "player" else "player"] = 0
            self.game_log(f"🏆 {winner.upper()} INSANELY CLAIMS AUTOMATIC VICTORY", "system")
            self.check_game_over()
            return

        damage = self.state["base_damage"]
        if self.state["statuses"][attacker]["burn"] > 0: damage = max(1, damage // 2)
        if self.state["rules"]["guns_enabled"]:
            damage += 10
            self.game_log("💥 Guns are blazing!", "combat")
        if self.state["rules"]["double_damage"]: damage *= 2
        if self.state["rules"]["sudden_death"]: damage *= 3
        if self.state["rules"]["random_damage_spike"]: damage *= random.randint(1, 4)
        if self.state["rules"]["crit_boost"] and random.random() < 0.4:
            self.game_log("✨ CRITICAL HIT EMITTED!", "system")
            damage *= 2

        if trivia_result == "correct": damage *= 2
        elif trivia_result == "wrong": damage = max(1, damage // 2)

        damage = int(damage)
        defense = 0 if self.state["rules"].get("armor_pierce") else (self.state["player_defense"] if defender == "player" else self.state["cpu_defense"])
        
        if self.state["rules"]["reverse_damage"]:
            actual_change = -damage 
            self.game_log(f"❤️ Reverse Damage active! {defender.upper()} absorbs structural points.")
        else:
            actual_change = max(0, damage - defense)

        self.state[f"{defender}_hp"] -= actual_change
        self.game_log(f"⚔️ {attacker.upper()} strikes! Shifts balance by {actual_change} to {defender.upper()}.", "combat")
        if self.check_game_over(): return
            
        self.trigger_damage_cutscene(defender, actual_change)
        
        if self.state["rules"].get("life_steal") and actual_change > 0:
            heal = actual_change // 2
            self.state[f"{attacker}_hp"] += heal
            self.game_log(f"🩸 Life Steal: {attacker.upper()} recovered {heal} HP", "victory")
            
        if self.state["rules"].get("damage_reflect") and actual_change > 0:
            reflect = max(3, actual_change // 3)
            self.state[f"{attacker}_hp"] -= reflect
            self.game_log(f"🔄 Damage Reflect! {attacker.upper()} took {reflect} backlash damage!", "combat")
            if self.check_game_over(): return

        self.apply_status_roll(defender)
        if self.check_game_over(): return
        self.update_status_displays()

    def run_cpu_turn(self):
        if not self.game_active: return
        if not self.check_can_act("cpu"):
            self.run_upkeep_phase()
            return

        if self.state["rules"]["rps_mode"]:
            opts = ["rock", "paper", "scissors"]
            cpu_choice = random.choice(opts)
            self.game_log("🤖 CPU is targeting your position! Defend in Rock Paper Scissors Mode.")
            self.clear_action_space()
            for move in opts:
                btn = tk.Button(self.action_area, text=move.upper(), bg="#4b2a4a", fg="white", font=("Courier", 12),
                                command=lambda m=move: self.resolve_rps("cpu", "player", cpu_choice, m))
                btn.pack(side="left", expand=True, padx=10, pady=10)
        else:
            self.try_trivia("cpu", lambda outcome: [self.execute_strike("cpu", "player", outcome), 
                                                   self.root.after(1000, self.run_upkeep_phase) if self.game_active else None])

    def run_player_turn(self):
        if not self.game_active: return
        self.clear_action_space()
        if self.check_game_over(): return
        self.update_status_displays()
        self.processing_turn = False
        
        if not self.check_can_act("player"):
            self.root.after(1000, self.run_cpu_turn)
            return

        if self.state["rules"]["rps_mode"]:
            self.game_log("✂️ 📄 🪨 RPS SYSTEM ACTIVE. CHOOSE DEFENSE SYMBOL:")
            for move in ["rock", "paper", "scissors"]:
                btn = tk.Button(self.action_area, text=move.upper(), bg="#2a4d69", fg="white", font=("Courier", 12),
                                command=lambda m=move: self.resolve_rps("player", "cpu", m, random.choice(["rock", "paper", "scissors"])))
                btn.pack(side="left", expand=True, padx=10, pady=10)
        else:
            atk_btn = tk.Button(self.action_area, text="LAUNCH STRIKE", font=("Courier", 14, "bold"), bg="#c0392b", fg="white",
                                command=self.player_attack_clicked)
            atk_btn.pack(fill="both", expand=True, padx=20, pady=20)

    def player_attack_clicked(self):
        if not self.game_active or self.processing_turn: return
        self.processing_turn = True
        self.clear_action_space()
        self.try_trivia("player", lambda outcome: [self.execute_strike("player", "cpu", outcome), 
                                                   self.root.after(1000, self.run_cpu_turn) if self.game_active else None])

    def resolve_rps(self, attacker, defender, choice, def_choice):
        if not self.game_active: return
        self.clear_action_space()
        self.game_log(f"{attacker.upper()} deployed {choice.upper()}! {defender.upper()} countered with {def_choice.upper()}!")
        win_conditions = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
        
        if choice == def_choice:
            self.game_log("🤝 Mutual Parity! No structural impact sustained.", "normal")
        elif win_conditions[choice] == def_choice:
            dmg = self.state["base_damage"] * 3
            self.game_log(f"🎯 {attacker.upper()} DOMINATED MATCHUP! Deals {dmg} fatal damage!", "victory")
            self.state[f"{defender}_hp"] -= dmg
            if self.check_game_over(): return
            self.trigger_damage_cutscene(defender, dmg)
        else:
            self.game_log(f"🛡️ {defender.upper()} DEFLECTED THE OUTCOME!", "combat")
            
        if self.check_game_over(): return
        self.update_status_displays()
        self.root.after(1000, self.run_cpu_turn if attacker == "player" else self.run_upkeep_phase)

    def run_upkeep_phase(self):
        if not self.game_active: return
        self.game_log("\n⏳ Round Upkeep Processing...", "normal")
        
        for actor in ["player", "cpu"]:
            s = self.state["statuses"][actor]
            if s["poison"] > 0 or self.state["rules"].get("poison_all"):
                dmg = 5 if s["poison"] > 0 else 3
                self.game_log(f"🍄 {actor.upper()} suffers {dmg} Poison damage.")
                self.state[f"{actor}_hp"] -= dmg
                if s["poison"] > 0: s["poison"] -= 1
                    
            if s["burn"] > 0:
                self.game_log(f"🔥 {actor.upper()} suffers 3 Burn thermal damage.")
                self.state[f"{actor}_hp"] -= 3
                s["burn"] -= 1
                
        if self.state["rules"]["regen"]:
            self.state["player_hp"] += self.state["regen_value"]
            self.state["cpu_hp"] += self.state["regen_value"]
            self.game_log(f"⏳ Nano-regeneration injected (+{self.state['regen_value']} HP global recovery)")

        if self.bomb_timer is not None:
            self.bomb_timer -= 1
            self.game_log(f"💣 Bomb Fuse Warning: {self.bomb_timer} ticks until core meltdown!", "system")
            if self.bomb_timer <= 0:
                self.game_log("\n💣💥 PAYLOAD HAS DETONATED. INSTABILITY RESULTED IN A DRAW.", "combat")
                messagebox.showinfo("MATRIX DESTROYED", "The ticking payload detonated! Game Result: DRAW.")
                self.shutdown_application()
                return

        if self.check_game_over(): return
        self.update_status_displays()

        if self.state["turn"] % 2 == 0: self.run_mutation_phase()
        else:
            self.state["turn"] += 1
            self.run_player_turn()

    # =====================================================================
    # SAFE HOOK MUTATION SEQUENCER
    # =====================================================================
    def apply_mutation(self, mutation, who):
        if not self.game_active: return
        self.game_log(f"⚡ {who.upper()} INJECTS OVERRIDE: {mutation}", "system")

        if mutation == "HARDCORE_MODE":
            self.game_log("☠️ HARDCORE INTERFACES LOADED! SYSTEM ADJUSTING...", "combat")
            self.processing_turn = True
            self.clear_action_space()
            
            # Safe reset values to prevent race conditions
            self.state["player_hp"] = 15
            self.state["cpu_hp"] = 150
            self.clear_rules_dict()
            self.update_status_displays()
            self.root.after(800, lambda: self.hardcore_pick_two())
            return

        elif mutation == "ARMOR_PIERCE": self.state["rules"]["armor_pierce"] = True
        elif mutation == "LIFE_STEAL": self.state["rules"]["life_steal"] = True
        elif mutation == "DAMAGE_REFLECT": self.state["rules"]["damage_reflect"] = True
        elif mutation == "TIME_WARP":
            self.state["turn"] += 1  
            self.game_log("⏭️ Time Warp: Next mutation phase skipped!")
        elif mutation == "POISON_ALL": self.state["rules"]["poison_all"] = True
        elif mutation == "ENABLE_TRIVIA": self.state["rules"]["trivia"] = True
        elif mutation == "ENABLE_GUNS": self.state["rules"]["guns_enabled"] = True
        elif mutation == "DISABLE_GUNS": self.state["rules"]["guns_enabled"] = False
        elif mutation == "DOUBLE_DAMAGE": self.state["rules"]["double_damage"] = True
        elif mutation == "HALF_DAMAGE": self.state["base_damage"] = max(1, self.state["base_damage"] // 2)
        elif mutation == "ADD_REGEN":
            self.state["rules"]["regen"] = True
            self.state["regen_value"] = 2
        elif mutation == "SUDDEN_DEATH":
            self.state["rules"]["sudden_death"] = True
            self.state["player_hp"] = min(self.state["player_hp"], 30)
            self.state["cpu_hp"] = min(self.state["cpu_hp"], 30)
        elif mutation == "INCREASE_PLAYER_HP": self.state["player_hp"] += 20
        elif mutation == "INCREASE_CPU_HP": self.state["cpu_hp"] += 20
        elif mutation == "DECREASE_PLAYER_HP": self.state["player_hp"] -= 10
        elif mutation == "DECREASE_CPU_HP": self.state["cpu_hp"] -= 10
        elif mutation == "INCREASE_BASE_DAMAGE": self.state["base_damage"] += 2
        elif mutation == "DECREASE_BASE_DAMAGE": self.state["base_damage"] = max(1, self.state["base_damage"] - 2)
        elif mutation == "REVERSE_DAMAGE": self.state["rules"]["reverse_damage"] = True
        elif mutation == "ENABLE_SHIELDS":
            self.state["player_defense"] += 2
            self.state["cpu_defense"] += 2
        elif mutation == "CRIT_BOOST": self.state["rules"]["crit_boost"] = True
        elif mutation == "CRIT_REDUCE": self.state["rules"]["crit_boost"] = False
        elif mutation == "SWAP_HP": self.state["player_hp"], self.state["cpu_hp"] = self.state["cpu_hp"], self.state["player_hp"]
        elif mutation == "STEAL_HP":
            t = "player" if who == "player" else "cpu"
            o = "cpu" if who == "player" else "player"
            self.state[f"{t}_hp"] += 10; self.state[f"{o}_hp"] -= 10
        elif mutation == "HP_EQUALISE":
            avg = (self.state["player_hp"] + self.state["cpu_hp"]) // 2
            self.state["player_hp"] = self.state["cpu_hp"] = avg
        elif mutation == "GLOBAL_DAMAGE_BOOST": self.state["base_damage"] += 3
        elif mutation == "GLOBAL_DAMAGE_REDUCE": self.state["base_damage"] = max(1, self.state["base_damage"] - 3)
        elif mutation == "RANDOM_DAMAGE_SPIKE": self.state["rules"]["random_damage_spike"] = True
        elif mutation == "LOW_HP_WIN": self.state["rules"]["low_hp_win"] = True
        elif mutation == "HIGH_HP_WIN": self.state["rules"]["high_hp_win"] = True
        elif mutation == "ENABLE_RPS": self.state["rules"]["rps_mode"] = True
        elif mutation == "BOMB_INSTALL": self.bomb_timer = random.randint(6, 15)
        elif mutation == "BOMB_ACCELERATE":
            if self.bomb_timer is not None: self.bomb_timer = max(1, self.bomb_timer - 3)
        elif mutation == "BOMB_SLOW":
            if self.bomb_timer is not None: self.bomb_timer += 3
        elif mutation == "INFUSE_POISON": self.state["rules"]["infuse_poison"] = True
        elif mutation == "INFUSE_BURN": self.state["rules"]["infuse_burn"] = True
        elif mutation == "INFUSE_SLEEP": self.state["rules"]["infuse_sleep"] = True
        elif mutation == "INFUSE_PARALYZE": self.state["rules"]["infuse_paralyze"] = True
        elif mutation == "INFUSE_FREEZE": self.state["rules"]["infuse_freeze"] = True
        elif mutation == "INFUSE_ACID": self.state["rules"]["infuse_acid"] = True
        elif mutation == "ENABLE_50_50": self.state["rules"]["fifty_fifty"] = True
        elif mutation == "DEFUSE_EFFECTS":
            for k in self.state["rules"]:
                if "infuse" in k: self.state["rules"][k] = False
        elif mutation == "PENALTY_SHOOTOUT_LTM":
            self.play_penalty_shootout(who, "cpu" if who == "player" else "player")
        elif mutation == "RED_CARD_LTM":
            target = "cpu" if who == "player" else "player"
            self.state["statuses"][target]["sleep"] = 2
            self.game_log(f"🟥 RED CARD! {target.upper()} sent off for 2 rounds!", "combat")
        elif mutation == "OVERCHARGE_LTM": self.state["base_damage"] += 15
        elif mutation == "NANITE_SHIELD_LTM": self.state[f"{who}_defense"] += 10
        elif mutation == "VAMPIRE_FANG_LTM":
            target = "cpu" if who == "player" else "player"
            self.state[f"{who}_hp"] += 25; self.state[f"{target}_hp"] -= 25
        elif mutation == "ECLIPSE_LTM": self.state["rules"]["reverse_damage"] = not self.state["rules"]["reverse_damage"]
        elif mutation == "SINGULARITY_LTM":
            self.state["player_hp"] = random.randint(10, 150)
            self.state["cpu_hp"] = random.randint(10, 150)
                
        if self.check_game_over(): return
        self.update_status_displays()

    def hardcore_pick_two(self):
        if not self.game_active: return
        self.game_log("🛡️ HARDCORE SURVIVAL DRAFT: Pick 2 options to build context...", "system")
        health_mutations = {"INCREASE_PLAYER_HP", "DECREASE_PLAYER_HP", "INCREASE_CPU_HP", "DECREASE_CPU_HP", "SWAP_HP", "STEAL_HP", "HP_EQUALISE"}
        
        # Filter out vaulted cards from the hardcore draft pool
        all_options = [m for m in MUTATION_WEIGHTS.keys() if m not in health_mutations and m not in self.vaulted_cards]
        options = random.sample(all_options, min(6, len(all_options)))
        
        self.clear_action_space()
        container = tk.Frame(self.action_area, bg="#121212")
        container.pack(expand=True, fill="both")
        picked = []
        
        def pick(mut):
            if mut in picked: return
            picked.append(mut)
            self.apply_mutation(mut, "player")
            if len(picked) == 2:
                self.clear_action_space()
                self.state["turn"] = 1
                self.run_player_turn()
            else: lbl.config(text=f"Choose mutation {len(picked)+1}/2")
        
        lbl = tk.Label(container, text="Choose mutation 1/2", font=("Courier", 14, "bold"), fg="#ffcc00", bg="#121212")
        lbl.pack(pady=10)
        for m in options:
            card = self.create_graphic_card(container, m, pick)
            card.pack(side="left", padx=10, pady=10, expand=True)

    def run_mutation_phase(self):
        if not self.game_active: return
        self.clear_action_space()
        self.game_log("\n⚡ ARENA MUTATION SEQUENCE ENGAGED ⚡", "system")
        
        first, second = ("player", "cpu") if self.mutation_turn_toggle else ("cpu", "player")
        self.mutation_turn_toggle = not self.mutation_turn_toggle
        
        def process_second_actor():
            if not self.game_active: return
            if second == "player": self.render_player_mutation_cards(lambda: advance_round())
            else:
                self.apply_mutation(self.get_weighted_mutations(1)[0], "cpu")
                advance_round()

        def advance_round():
            if not self.game_active: return
            self.state["turn"] += 1
            self.run_player_turn()

        if first == "player": self.render_player_mutation_cards(process_second_actor)
        else:
            self.apply_mutation(self.get_weighted_mutations(1)[0], "cpu")
            self.root.after(1000, process_second_actor)

    def render_player_mutation_cards(self, next_step_callback):
        if not self.game_active: return
        self.clear_action_space()
        
        rnd_options = self.get_weighted_mutations(5)
        available_cards = rnd_options + self.state["player_deck"]
        
        card_container = tk.Frame(self.action_area, bg="#121212")
        card_container.pack(expand=True, fill="both")
        
        def select_card(name):
            if name in self.state["player_deck"] and name not in rnd_options:
                self.state["player_deck"].remove(name)
            self.apply_mutation(name, "player")
            self.clear_action_space()
            next_step_callback()
            
        for mutation in available_cards:
            card = self.create_graphic_card(card_container, mutation, select_card)
            card.pack(side="left", padx=8, pady=10, expand=True)

    # =====================================================================
    # LAYOUT ENGINE SCREEN CONTROLLERS WITH DYNAMIC EVENT TRACKING
    # =====================================================================
    def update_draft_banner_loop(self):
        if not self.draft_frame or not self.draft_frame.winfo_exists(): return
        ev = self.get_current_event_state()
        
        if not ev["active"]:
            self.event_banner_lbl.config(text="📡 SEASON COMPLETE: Standby for Season 2 deployment protocols.", bg="#1a1a1a", fg="#cccccc")
            return

        # Handle the 4-week calendar text layouts
        if ev["weekend"]:
            banner_text = f"🔥 BATTLE PASS EVENT LIVE: {ev['label']} ({ev['multiplier']}X XP)! | Season Ends In: {ev['cd']}"
            self.event_banner_lbl.config(text=banner_text, bg="#3a0000", fg="#ff3333")
            
            # Context Hook: Unlock Season 2 pass workspace designs during the Week 4 10X Finale
            if ev["base_multiplier"] == 10:
                banner_text += " [S2 DESIGN COMPONENT ACTIVE]"
                self.event_banner_lbl.config(text=banner_text)
        else:
            # Weekend countdown parsing logic
            now = datetime.now(timezone.utc)
            time_until = ev["wknd_start"] - now
            hours, remainder = divmod(int(time_until.total_seconds()), 3600)
            minutes, seconds = divmod(remainder, 60)
            
            # Format text based on upcoming weight rewards
            upcoming_tag = f"{ev['base_multiplier']}X XP Weekend" if ev["base_multiplier"] > 1 else "Standard Event Block"
            banner_text = f"⏳ UPCOMING WEEKEND: {upcoming_tag} starts in {time_until.days}d {hours:02d}h {minutes:02d}m | Season Timer: {ev['cd']}"
            self.event_banner_lbl.config(text=banner_text, bg="#2c1a04", fg="#ffa502")
            
        self.root.after(1000, self.update_draft_banner_loop)

    def execute_deck_draft_gui(self):
        self.draft_frame = tk.Frame(self.root, bg="#121212")
        self.draft_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.event_banner_lbl = tk.Label(self.draft_frame, text="", font=("Courier", 11, "bold"), pady=6)
        self.event_banner_lbl.pack(fill="x", side="top")
        self.update_draft_banner_loop()
        
        control_banner = tk.Frame(self.draft_frame, bg="#1a1a1a", height=80)
        control_banner.pack(fill="x", side="top")
        
        hdr = tk.Label(control_banner, text="🃏 DECK DRAFTING MATRIX 🃏", font=("Courier", 18, "bold"), fg="#ffcc00", bg="#1a1a1a")
        hdr.pack(side="left", padx=20, pady=10)
        
        ev = self.get_current_event_state()
        if ev["active"] and ev["weekend"] and ev["base_multiplier"] == 10:
            pass_text = "🎨 DESIGN SEASON 2 PASS"
            bg_c = "#005f73"
            fg_c = "#94d2bd"
        else:
            pass_text = "👾 VIEW SEASON PASS"
            bg_c = "#431f5c"
            fg_c = "#e056fd"

        pass_btn = tk.Button(control_banner, text=pass_text, font=("Courier", 11, "bold"), bg=bg_c, fg=fg_c,
                             command=self.display_season_pass_gui)
        pass_btn.pack(side="right", padx=20, pady=15)
        
        self.counter_lbl = tk.Label(self.draft_frame, text=f"Selected Requirements: {len(self.state['player_deck'])} / 3", font=("Courier", 13), fg="#ffffff", bg="#121212")
        self.counter_lbl.pack(pady=10)
        
        scroll_canvas = tk.Canvas(self.draft_frame, bg="#1c1c1c", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.draft_frame, orient="vertical", command=scroll_canvas.yview)
        grid_frame = tk.Frame(scroll_canvas, bg="#1c1c1c")
        
        grid_frame.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        scroll_canvas.configure(yscrollcommand=scrollbar.set)
        
        scroll_canvas.pack(side="left", fill="both", expand=True, padx=30, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Build list of mutations, ensuring we completely exclude any cards currently vaulted from the master pool
        all_muts = [m for m in (list(MUTATION_WEIGHTS.keys()) + [r["id"] for r in SEASON_PASS_REWARDS]) if m not in self.vaulted_cards]
        
        def draft_pick(name):
            if len(self.state["player_deck"]) < 3 and name not in self.state["player_deck"]:
                self.state["player_deck"].append(name)
                self.counter_lbl.config(text=f"Selected Requirements: {len(self.state['player_deck'])} / 3")
                if len(self.state["player_deck"]) == 3:
                    self.draft_frame.destroy()
                    if self.pass_frame: self.pass_frame.destroy()
                    self.initialize_battlefield_gui()

        for index, mutation in enumerate(all_muts):
            card = self.create_graphic_card(grid_frame, mutation, draft_pick)
            card.grid(row=index // 4, column=index % 4, padx=15, pady=15)

    def display_season_pass_gui(self):
        if self.draft_frame: self.draft_frame.place_forget()
        self.pass_frame = tk.Frame(self.root, bg="#0d0d11")
        self.pass_frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        top_bar = tk.Frame(self.pass_frame, bg="#161623", height=70)
        top_bar.pack(fill="x", side="top")
        
        ev = self.get_current_event_state()
        is_s2_active = ev["active"] and ev["weekend"] and ev["base_multiplier"] == 10
        
        title_txt = "🎨 SEASON 2 BLUEPRINT ARCHITECT" if is_s2_active else "⚡ SEASON 1 BATTLE PASS ⚡"
        title_lbl = tk.Label(top_bar, text=title_txt, font=("Courier", 18, "bold"), fg="#00d2d3", bg="#161623")
        title_lbl.pack(side="left", padx=20, pady=15)
        
        return_btn = tk.Button(top_bar, text="⬅️ RETURN TO DECK DRAFT", font=("Courier", 11, "bold"), bg="#222f3e", fg="#c8d6e5",
                               command=self.hide_season_pass_gui)
        return_btn.pack(side="right", padx=20, pady=15)
        
        xp_container = tk.Frame(self.pass_frame, bg="#1a1a24", highlightbackground="#333344", highlightthickness=1)
        xp_container.pack(fill="x", padx=40, pady=20)
        
        xp_status_text = f"S2 Concept Draft Active | Profile Anchor: {self.player_xp} XP" if is_s2_active else f"Profile Progression Status: {self.player_xp} Total S1_XP"
        xp_info_lbl = tk.Label(xp_container, text=xp_status_text, font=("Courier", 13, "bold"), fg="#ffffff", bg="#1a1a24")
        xp_info_lbl.pack(anchor="w", padx=15, pady=10)
        
        bar_bg = tk.Frame(xp_container, bg="#2d2d3d", height=25)
        bar_bg.pack(fill="x", padx=15, pady=10)
        
        progress_fill = tk.Frame(bar_bg, bg="#ff9f43" if is_s2_active else "#00d2d3", height=25)
        progress_fill.place(relx=0, rely=0, relwidth=min(1.0, self.player_xp / 1200), relheight=1)
        
        rewards_scroll_canvas = tk.Canvas(self.pass_frame, bg="#0d0d11", highlightthickness=0)
        rewards_scrollbar = tk.Scrollbar(self.pass_frame, orient="vertical", command=rewards_scroll_canvas.yview)
        rewards_grid = tk.Frame(rewards_scroll_canvas, bg="#0d0d11")
        
        rewards_grid.bind("<Configure>", lambda e: rewards_scroll_canvas.configure(scrollregion=rewards_scroll_canvas.bbox("all")))
        rewards_scroll_canvas.create_window((0, 0), window=rewards_grid, anchor="nw")
        rewards_scroll_canvas.configure(yscrollcommand=rewards_scrollbar.set)
        
        rewards_scroll_canvas.pack(side="left", fill="both", expand=True, padx=40, pady=10)
        rewards_scrollbar.pack(side="right", fill="y")
        
        # Load Season 1 items or prototype structural fields for Season 2 blocks
        display_dataset = [
            {"tier": i+1, "xp_required": (i+1)*200, "id": f"S2_PROTOTYPE_{i+1}_LTM", "desc": "Experimental Season 2 payload modification matrix."}
            for i in range(5)
        ] if is_s2_active else SEASON_PASS_REWARDS

        for item in display_dataset:
            unlocked = self.player_xp >= item["xp_required"]
            status_color = "#94d2bd" if is_s2_active else ("#00d2d3" if unlocked else "#ff7675")
            status_txt = "[S2 PROTOTYPE DESIGN]" if is_s2_active else ("✔️ UNLOCKED" if unlocked else f"🔒 LOCK: {item['xp_required']} XP")
            
            row_item = tk.Frame(rewards_grid, bg="#161623", highlightbackground="#333344", highlightthickness=1, width=820, height=80)
            row_item.pack(fill="x", pady=8, padx=5)
            row_item.pack_propagate(False)
            
            tk.Label(row_item, text=f"TIER {item['tier']}", font=("Courier", 14, "bold"), fg="#ff9f43", bg="#161623").pack(side="left", padx=15)
            meta = tk.Frame(row_item, bg="#161623")
            meta.pack(side="left", fill="both", pady=10, padx=10)
            
            tk.Label(meta, text=item["id"].replace("_", " "), font=("Courier", 12, "bold"), fg="#ffffff", bg="#161623").pack(anchor="w")
            tk.Label(meta, text=item["desc"], font=("Courier", 9), fg="#a4b0be", bg="#161623").pack(anchor="w")
            tk.Label(row_item, text=status_txt, font=("Courier", 11, "bold"), fg=status_color, bg="#161623").pack(side="right", padx=20)

    def hide_season_pass_gui(self):
        if self.pass_frame: self.pass_frame.destroy()
        if self.draft_frame: self.draft_frame.place(relx=0, rely=0, relwidth=1, relheight=1)

    def initialize_battlefield_gui(self):
        hud = tk.Frame(self.root, bg="#1a1a1a", height=100, highlightbackground="#333333", highlightthickness=1)
        hud.pack(fill="x", side="top")
        hud.pack_propagate(False)
        
        self.turn_lbl = tk.Label(hud, text="ROUND 1", font=("Courier", 18, "bold"), fg="#ffcc00", bg="#1a1a1a")
        self.turn_lbl.pack(pady=5)
        self.global_rules_lbl = tk.Label(hud, text="", font=("Courier", 10), fg="#cccccc", bg="#1a1a1a")
        self.global_rules_lbl.pack()
        self.rules_lbl = tk.Label(hud, text="Global Mutations: None", font=("Courier", 10, "italic"), fg="#e056fd", bg="#1a1a1a")
        self.rules_lbl.pack(pady=2)

        arena_view = tk.Frame(self.root, bg="#121212")
        arena_view.pack(fill="both", expand=True, pady=10)
        
        self.player_panel = tk.Frame(arena_view, bg="#1e272c", highlightbackground="#2a4d69", highlightthickness=3)
        self.player_panel.pack(side="left", expand=True, fill="both", padx=20, pady=10)
        tk.Label(self.player_panel, text="OPERATOR (PLAYER)", font=("Courier", 14, "bold"), fg="#4fc3f7", bg="#1e272c").pack(pady=10)
        self.p_hp_lbl = tk.Label(self.player_panel, text="HP: 150", font=("Courier", 22, "bold"), fg="#ffffff", bg="#1e272c")
        self.p_hp_lbl.pack(expand=True)

        self.cpu_panel = tk.Frame(arena_view, bg="#2c1e2b", highlightbackground="#4b2a4a", highlightthickness=3)
        self.cpu_panel.pack(side="right", expand=True, fill="both", padx=20, pady=10)
        tk.Label(self.cpu_panel, text="CENTRAL UNIT (CPU)", font=("Courier", 14, "bold"), fg="#f06292", bg="#2c1e2b").pack(pady=10)
        self.c_hp_lbl = tk.Label(self.cpu_panel, text="HP: 150", font=("Courier", 22, "bold"), fg="#ffffff", bg="#2c1e2b")
        self.c_hp_lbl.pack(expand=True)

        log_container = tk.Frame(self.root, bg="#1a1a1a", height=150)
        log_container.pack(fill="x", padx=20, pady=5)
        log_container.pack_propagate(False)
        
        self.log_box = tk.Text(log_container, bg="#0a0a0a", fg="#ffffff", font=("Courier", 10), state='disabled', wrap='word')
        self.log_box.pack(fill="both", expand=True)
        self.init_log_tags()

        self.action_area = tk.Frame(self.root, bg="#1a1a1a", height=220, highlightbackground="#333333", highlightthickness=1)
        self.action_area.pack(fill="x", side="bottom", padx=20, pady=10)
        self.action_area.pack_propagate(False)

        self.update_status_displays()
        self.run_player_turn()

if __name__ == "__main__":
    main_root = tk.Tk()
    app = MutationArenaApp(main_root)
    app.execute_deck_draft_gui()
    main_root.mainloop()
