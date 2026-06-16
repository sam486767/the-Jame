import threading
import random
import sys
import time
import tkinter as tk
from tkinter import messagebox, simpledialog
import updater

# Keep background updater intact
running = True
update_requested = False

def request_game_shutdown():
    global update_requested
    update_requested = True

def start_updater():
    updater.run_updater(request_game_shutdown)

threading.Thread(target=start_updater, daemon=True).start()

# =========================
# GAME STATE & WEIGHTS
# =========================

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
    "PENALTY_SHOOTOUT_LTM": 3, "RED_CARD_LTM": 2
}

state = {
    "player_hp": 150, "cpu_hp": 150, "base_damage": 10,
    "player_defense": 0, "cpu_defense": 0, "turn": 1, "player_deck": [],
    "statuses": {
        "player": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False},
        "cpu": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False}
    },
    "rules": {
        "guns_enabled": False, "trivia": False, "double_damage": False, "regen": False,
        "sudden_death": False, "reverse_damage": False, "random_damage_spike": False,
        "crit_boost": False, "low_hp_win": False, "high_hp_win": False, "rps_mode": False,
        "infuse_poison": False, "infuse_burn": False, "infuse_sleep": False,
        "infuse_paralyze": False, "infuse_freeze": False, "infuse_acid": False, "fifty_fifty": False
    },
    "regen_value": 0
}

bomb_timer = None
mutation_turn_toggle = True
TRIVIA = [
    {"q": "What is 2 + 2?", "a": "4"},
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "What planet do we live on?", "a": "earth"},
    {"q": "What is 10 / 2?", "a": "5"},
    {"q": "What colour is the sky on a clear day?", "a": "blue"}
]

# Shared layouts globally monitored by control scopes
player_panel = None
cpu_panel = None
p_hp_lbl = None
c_hp_lbl = None
turn_lbl = None
global_rules_lbl = None
rules_lbl = None
log_box = None
action_area = None

# =========================
# CORE UTILITY METHODS
# =========================

def get_weighted_mutations(k):
    population = list(MUTATION_WEIGHTS.keys())
    weights = list(MUTATION_WEIGHTS.values())
    chosen = []
    for _ in range(min(k, len(population))):
        c = random.choices(population, weights=weights, k=1)[0]
        idx = population.index(c)
        chosen.append(c)
        population.pop(idx)
        weights.pop(idx)
    return chosen

# =========================
# TKINTER ENGINE LAYOUT
# =========================

root = tk.Tk()
root.title("MUTATION ARENA: CARD EDITION")
root.geometry("900x700")
root.configure(bg="#121212")

# Check for updater thread requests
def check_updater_signals():
    if update_requested:
        root.destroy()
        sys.exit()
    root.after(500, check_updater_signals)

# Text Log Display Controller with NoneType Safety
def game_log(message, color="#ffffff"):
    print(message)  # Fallback to standard terminal out
    if log_box is not None:
        try:
            log_box.configure(state='normal')
            tag_name = "color_" + str(time.time()).replace(".", "_")
            log_box.tag_config(tag_name, foreground=color)
            log_box.insert(tk.END, message + "\n", tag_name)
            log_box.see(tk.END)
            log_box.configure(state='disabled')
        except Exception:
            pass

# Synchronize backend state numbers to GUI visuals
def update_status_displays():
    if p_hp_lbl and c_hp_lbl and turn_lbl and global_rules_lbl and rules_lbl:
        p_hp_lbl.config(text=f"HP: {state['player_hp']}")
        c_hp_lbl.config(text=f"HP: {state['cpu_hp']}")
        turn_lbl.config(text=f"ROUND {state['turn']}")
        
        stats_text = f"Base Attack Value: {state['base_damage']}  |  Shield Capacity (P/C): {state['player_defense']}/{state['cpu_defense']}"
        if bomb_timer is not None:
            stats_text += f"  |  💣 BOMB COUNTDOWN: {bomb_timer}"
        global_rules_lbl.config(text=stats_text)
        
        # Render active rules text
        active_rules = [k for k, v in state["rules"].items() if v]
        rules_lbl.config(text="Global Mutations: " + (", ".join(active_rules) if active_rules else "None"))

# =========================
# VISUAL CUTSCENES & ANIMATIONS
# =========================

def trigger_damage_cutscene(target, damage_dealt):
    """Executes a graphic sequence including red screens, screen shaking, and rising impact text."""
    target_frame = player_panel if target == "player" else cpu_panel
    if not target_frame:
        return
        
    original_bg = target_frame.cget("bg")
    
    # Cutscene Component A: Flashing Crimson Threat
    def flash(count):
        if count <= 0:
            target_frame.config(bg=original_bg)
            return
        current_color = "#b21c1c" if count % 2 == 0 else original_bg
        target_frame.config(bg=current_color)
        root.after(60, lambda: flash(count - 1))

    # Cutscene Component B: Positional Screen Shake
    def shake(step, current_x=0):
        if step <= 0:
            target_frame.pack_configure(padx=20)
            return
        offset = random.choice([-12, 12])
        target_frame.pack_configure(padx=20 + offset)
        root.after(40, lambda: shake(step - 1, offset))

    # Cutscene Component C: Floating Combat Text Burst
    popup = tk.Label(target_frame, text=f"-{damage_dealt} HP!", font=("Courier", 24, "bold"), bg="#121212", fg="#ff3333")
    popup.place(relx=0.5, rely=0.3, anchor="center")
    
    def float_up(ticks, current_y=0.3):
        if ticks <= 0:
            popup.destroy()
            return
        popup.place(relx=0.5, rely=current_y - 0.02, anchor="center")
        root.after(50, lambda: float_up(ticks - 1, current_y - 0.02))

    flash(5)
    shake(8)
    float_up(12)

# =========================
# GRAPHICAL CARD UTILITIES
# =========================

def clear_action_space():
    if action_area:
        for widget in action_area.winfo_children():
            widget.destroy()

def get_card_design(mutation_key):
    """
    Parses a mutation key to strip '_LTM' tags and returns a tuple of layout designs:
    (display_name, bg_color, border_color, text_color, hover_bg)
    """
    display_name = mutation_key
    is_ltm = False
    
    # 1. Handle LTM Tag Extraction
    if mutation_key.endswith("_LTM"):
        display_name = mutation_key[:-4]  # Remove "_LTM"
        is_ltm = True
        
    # Format text for UI layout presentation (replace underscores with clean spaces)
    display_name = display_name.replace("_", " ")
    
    # 2. Assign Border Styles and Rarity/Class Colors
    if is_ltm:
        # 👾 LIMITED TIME MODE CLASS (Vibrant Neon Purple/Magenta Theme)
        return display_name, "#2c1a3a", "#e056fd", "#e056fd", "#431f5c"
    
    # Keyword classification filters
    offensive_keywords = ["DAMAGE", "GUNS", "CRIT", "STRIKE", "INFUSE"]
    vitality_keywords = ["HP", "REGEN", "EQUALISE", "SHIELDS", "STEAL"]
    chaos_keywords = ["BOMB", "50_50", "RPS", "SWAP", "REVERSE"]
    
    if any(kw in mutation_key for kw in offensive_keywords):
        # 🔥 OFFENSIVE CLASS (Crimson / Red Theme)
        return display_name, "#2d1414", "#ff4757", "#ff4757", "#4a1c1c"
        
    elif any(kw in mutation_key for kw in vitality_keywords):
        # 🛡️ VITALITY & DEFENSE CLASS (Emerald / Green Theme)
        return display_name, "#112415", "#2ed573", "#2ed573", "#1b3d22"
        
    elif any(kw in mutation_key for kw in chaos_keywords):
        # 🎲 CHAOS & RISK CLASS (Cyber Gold / Amber Theme)
        return display_name, "#26210f", "#ffa502", "#ffa502", "#403714"
        
    # ⚙️ STANDARD UTILITY CLASS (Sleek Slate Blue Theme)
    return display_name, "#1e222b", "#70a1ff", "#70a1ff", "#2f3640"


def create_graphic_card(parent, title, command_callback):
    """Generates a custom graphic trading-card frame using explicit rarity classes and borders."""
    # Pull dynamic style configurations from the styling engine
    display_name, bg_color, border_color, text_color, hover_bg = get_card_design(title)
    
    # Core card structural boundary layout frame
    card = tk.Frame(parent, bg=bg_color, highlightbackground=border_color, highlightthickness=2, width=160, height=200)
    card.pack_propagate(False)
    
    # Internal centered text decoration
    lbl = tk.Label(card, text=display_name, font=("Courier", 11, "bold"), fg=text_color, bg=bg_color, wraplength=140)
    lbl.pack(expand=True, fill="both", padx=10, pady=10)
    
    # Click-binding integration (Passes original backend 'title' string, NOT the filtered UI text)
    def trigger_click(e): command_callback(title)
    card.bind("<Button-1>", trigger_click)
    lbl.bind("<Button-1>", trigger_click)
    
    # Hover animations tracking card category colors
    card.bind("<Enter>", lambda e: card.config(bg=hover_bg))
    card.bind("<Leave>", lambda e: card.config(bg=bg_color))
    lbl.bind("<Enter>", lambda e: [card.config(bg=hover_bg), lbl.config(bg=hover_bg)])
    lbl.bind("<Leave>", lambda e: [card.config(bg=bg_color), lbl.config(bg=bg_color)])
    
    return card

# =========================
# SYSTEM RULES PROCEDURES
# =========================

def check_game_over():
    p_dead = state["player_hp"] <= 0
    c_dead = state["cpu_hp"] <= 0

    if p_dead or c_dead:
        update_status_displays()
        title = "⚡ ARENA TERMINATION ⚡"
        msg = f"Final Standings:\nPlayer HP: {state['player_hp']} | CPU HP: {state['cpu_hp']}\n\n"
        
        if state["rules"]["low_hp_win"]:
            msg += "Condition 'LOW HP WIN' active!\n"
            if state["player_hp"] < state["cpu_hp"]: msg += "PLAYER WINS!"
            elif state["cpu_hp"] < state["player_hp"]: msg += "CPU WINS!"
            else: msg += "DRAW!"
        elif state["rules"]["high_hp_win"]:
            msg += "Condition 'HIGH HP WIN' active!\n"
            if state["player_hp"] > state["cpu_hp"]: msg += "PLAYER WINS!"
            elif state["cpu_hp"] > state["player_hp"]: msg += "CPU WINS!"
            else: msg += "DRAW!"
        elif p_dead and c_dead: msg += "MUTUAL DESTRUCTION - DRAW!"
        elif p_dead: msg += "CPU WINS!"
        else: msg += "PLAYER WINS!"
        
        messagebox.showinfo(title, msg)
        root.destroy()
        sys.exit()

def try_trivia(attacker, complete_callback):
    if not state["rules"]["trivia"] or random.random() > 0.25:
        complete_callback("pass")
        return

    q = random.choice(TRIVIA)
    game_log(f"❓ TRIVIA OVERRIDE ISSUED FOR {attacker.upper()}!", "#4fc3f7")
    
    if attacker == "cpu":
        ans = q["a"] if random.random() > 0.5 else "wrong_answer"
        game_log(f"CPU selected: {ans}")
        if ans == q["a"]:
            game_log("✔ CPU Answer Correct!", "#81c784")
            complete_callback("correct")
        else:
            game_log("✖ CPU Answer Incorrect!", "#e57373")
            complete_callback("wrong")
    else:
        # Prompt user through graphic popup instead of CLI stdin block
        user_ans = simpledialog.askstring("TRIVIA TIME!", f"Question: {q['q']}")
        user_ans = user_ans.strip().lower() if user_ans else ""
        if user_ans == q["a"]:
            game_log("✔ Player Answer Correct!", "#81c784")
            complete_callback("correct")
        else:
            game_log("✖ Player Answer Incorrect!", "#e57373")
            complete_callback("wrong")

def apply_status_roll(defender):
    chance = 0.3
    if state["rules"]["infuse_poison"] and random.random() < chance:
        state["statuses"][defender]["poison"] += 3
        game_log(f"🍄 {defender.upper()} was Poisoned for 3 turns!", "#a9dfbf")
    if state["rules"]["infuse_burn"] and random.random() < chance:
        state["statuses"][defender]["burn"] += 3
        game_log(f"🔥 {defender.upper()} was Burned for 3 turns!", "#f5b041")
    if state["rules"]["infuse_sleep"] and random.random() < chance:
        state["statuses"][defender]["sleep"] = random.randint(1, 2)
        game_log(f"💤 {defender.upper()} fell asleep!", "#aed6f1")
    if state["rules"]["infuse_paralyze"] and random.random() < chance:
        state["statuses"][defender]["paralyze"] = True
        game_log(f"⚡ {defender.upper()} is Paralyzed!", "#f9e79f")
    if state["rules"]["infuse_freeze"] and random.random() < chance:
        state["statuses"][defender]["freeze"] = True
        game_log(f"🧊 {defender.upper()} was Frozen solid!", "#5dedf5")
    if state["rules"]["infuse_acid"] and random.random() < chance:
        state["statuses"][defender]["poison"] += 1
        game_log(f"🧪 {defender.upper()} hit with Acid! (+1 turn Poison)", "#58d68d")

def check_can_act(actor):
    s = state["statuses"][actor]
    if s["sleep"] > 0:
        game_log(f"💤 {actor.upper()} is fast asleep...", "#5da2f5")
        s["sleep"] -= 1
        return False
    if s["freeze"]:
        if random.random() < 0.25:
            game_log(f"🧊✨ {actor.upper()} thawed out!", "#5dedf5")
            s["freeze"] = False
        else:
            game_log(f"🧊 {actor.upper()} is frozen solid!", "#5dedf5")
            return False
    if s["paralyze"]:
        if random.random() < 0.25:
            game_log(f"⚡ {actor.upper()} is fully paralyzed and skips action!", "#f9e79f")
            return False
    return True

def play_penalty_shootout(attacker, defender):
    """Triggers an immediate high-stakes penalty shootout mini-game using Tkinter dialog inputs."""
    game_log(f"\n⚽ {attacker.upper()} IS TAKING A PENALTY KICK!", "#e67e22")
    
    directions = ["left", "center", "right"]
    
    # 1. Striker Choice Selection Window
    if attacker == "player":
        strike = simpledialog.askstring("PENALTY KICK!", "Where do you shoot? (left/center/right):")
        if strike: strike = strike.strip().lower()
        while strike not in directions: 
            strike = simpledialog.askstring("INVALID DIRECTION", "Choose left, center, or right:")
            if strike: strike = strike.strip().lower()
        gk_save = random.choice(directions)
    else:
        strike = random.choice(directions)
        game_log("🤖 CPU is preparing to shoot...")
        gk_save = simpledialog.askstring("PENALTY SAVE!", "Which way do you dive to save? (left/center/right):")
        if gk_save: gk_save = gk_save.strip().lower()
        while gk_save not in directions: 
            gk_save = simpledialog.askstring("INVALID DIRECTION", "Choose left, center, or right:")
            if gk_save: gk_save = gk_save.strip().lower()

    game_log(f"👟 {attacker.upper()} shoots {strike.upper()}!", "#ffffff")
    game_log(f"🧤 {defender.upper()} dives {gk_save.upper()}!", "#ffffff")
    
    # 2. Outcome Calculations & Vector Shifts
    if strike == gk_save:
        game_log(f"❌ GREAT SAVE! {defender.upper()} blocked the shot! Counter-attack dealing 10 damage to {attacker.upper()}!", "#e74c3c")
        if attacker == "player": state["player_hp"] -= 10
        else: state["cpu_hp"] -= 10
        trigger_damage_cutscene(attacker, 10)
    else:
        goal_damage = max(35, state["base_damage"] * 6)
        game_log(f"⚽ GOAL!!! {attacker.upper()} completely fooled the keeper and scores {goal_damage} damage!", "#2ecc71")
        if defender == "player": state["player_hp"] -= goal_damage
        else: state["cpu_hp"] -= goal_damage
        trigger_damage_cutscene(defender, goal_damage)
        
    update_status_displays()
    check_game_over()

# =========================
# COMBAT FLIGHT CONTROL ENGINE
# =========================

def execute_strike(attacker, defender, trivia_result):
    if state["rules"]["fifty_fifty"]:
        game_log("\n🎲 50/50 ACTIVE — PURGING ALL COIN FLIPS", "#e74c3c")
        winner = random.choice(["player", "cpu"])
        loser = "cpu" if winner == "player" else "player"
        state[f"{loser}_hp"] = 0
        game_log(f"🏆 {winner.upper()} INSANELY CLAIMS AUTOMATIC VICTORY", "#ffcc00")
        check_game_over()
        return

    base = state["base_damage"]
    damage = base

    if state["statuses"][attacker]["burn"] > 0:
        damage = max(1, damage // 2)
    if state["rules"]["guns_enabled"]:
        damage += 10
        game_log("💥 Guns are blazing!", "#ff5722")
    if state["rules"]["double_damage"]: damage *= 2
    if state["rules"]["sudden_death"]: damage *= 3
    if state["rules"]["random_damage_spike"]: damage *= random.randint(1, 4)
    if state["rules"]["crit_boost"] and random.random() < 0.4:
        game_log("✨ CRITICAL HIT EMITTED!", "#ffeb3b")
        damage *= 2

    if trivia_result == "correct":
        damage *= 2
        game_log("🔥 Trivia Multiplier Boost active!")
    elif trivia_result == "wrong":
        damage = max(1, damage // 2)
        game_log("💀 Trivia Deficit penalty applied")

    damage = int(damage)
    defense = state["player_defense"] if defender == "player" else state["cpu_defense"]
    
    if state["rules"]["reverse_damage"]:
        actual_change = -damage 
        game_log(f"❤️ Reverse Damage active! {defender.upper()} absorbs fuel.", "#4caf50")
    else:
        actual_change = max(0, damage - defense)

    if defender == "player": state["player_hp"] -= actual_change
    else: state["cpu_hp"] -= actual_change

    game_log(f"⚔️ {attacker.upper()} strikes! Shifts balance by {actual_change} to {defender.upper()}.", "#ff7675")
    
    trigger_damage_cutscene(defender, actual_change)
    apply_status_roll(defender)
    update_status_displays()
    check_game_over()

def run_cpu_turn():
    if not check_can_act("cpu"):
        run_upkeep_phase()
        return

    if state["rules"]["rps_mode"]:
        opts = ["rock", "paper", "scissors"]
        cpu_choice = random.choice(opts)
        game_log("🤖 CPU is targeting your position! Defend in Rock Paper Scissors Mode.")
        
        clear_action_space()
        for move in opts:
            btn = tk.Button(action_area, text=move.upper(), bg="#4b2a4a", fg="white", font=("Courier", 12),
                            command=lambda m=move: resolve_rps("cpu", "player", cpu_choice, m))
            btn.pack(side="left", expand=True, padx=10, pady=10)
    else:
        try_trivia("cpu", lambda outcome: [execute_strike("cpu", "player", outcome), root.after(1000, run_upkeep_phase)])

def run_player_turn():
    clear_action_space()
    update_status_displays()
    
    if not check_can_act("player"):
        root.after(1000, run_cpu_turn)
        return

    if state["rules"]["rps_mode"]:
        game_log("✂️ 📄 🪨 RPS SYSTEM TRIGGERED. CHOOSE ATTACK OBJECTIVE:")
        opts = ["rock", "paper", "scissors"]
        for move in opts:
            btn = tk.Button(action_area, text=move.upper(), bg="#2a4d69", fg="white", font=("Courier", 12),
                            command=lambda m=move: resolve_rps("player", "cpu", m, random.choice(opts)))
            btn.pack(side="left", expand=True, padx=10, pady=10)
    else:
        atk_btn = tk.Button(action_area, text="LAUNCH STRIKE", font=("Courier", 14, "bold"), bg="#c0392b", fg="white",
                            command=player_attack_clicked)
        atk_btn.pack(fill="both", expand=True, padx=20, pady=20)

def player_attack_clicked():
    clear_action_space()
    try_trivia("player", lambda outcome: [execute_strike("player", "cpu", outcome), root.after(1000, run_cpu_turn)])

def resolve_rps(attacker, defender, choice, def_choice):
    clear_action_space()
    game_log(f"{attacker.upper()} deployed {choice.upper()}! {defender.upper()} countered with {def_choice.upper()}!")
    win_conditions = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    
    if choice == def_choice:
        game_log("🤝 Mutual Parity! Stalemate reached - No impact sustained.", "#bdc3c7")
    elif win_conditions[choice] == def_choice:
        dmg = state["base_damage"] * 3
        game_log(f"🎯 {attacker.upper()} DOMINATED MATCHUP! Deals {dmg} fatal damage!", "#2ecc71")
        state[f"{defender}_hp"] -= dmg
        trigger_damage_cutscene(defender, dmg)
    else:
        game_log(f"🛡️ {defender.upper()} DEFLECTED THE OUTCOME! Deflection protocols active.", "#e74c3c")
        
    update_status_displays()
    check_game_over()
    
    if attacker == "player":
        root.after(1000, run_cpu_turn)
    else:
        root.after(1000, run_upkeep_phase)

# =========================
# UPKEEP & MUTATION ENGINE MANAGEMENT
# =========================

def run_upkeep_phase():
    global bomb_timer
    game_log("\n⏳ Round Upkeep Processing...", "#95a5a6")
    
    for actor in ["player", "cpu"]:
        s = state["statuses"][actor]
        if s["poison"] > 0:
            game_log(f"🍄 {actor.upper()} suffers 5 Poison breakdown damage.")
            state[f"{actor}_hp"] -= 5
            s["poison"] -= 1
        if s["burn"] > 0:
            game_log(f"🔥 {actor.upper()} suffers 3 Burn thermal damage.")
            state[f"{actor}_hp"] -= 3
            s["burn"] -= 1
            
    if state["rules"]["regen"]:
        state["player_hp"] += state["regen_value"]
        state["cpu_hp"] += state["regen_value"]
        game_log(f"⏳ Nano-regeneration injected (+{state['regen_value']} HP global recovery)")

    if bomb_timer is not None:
        bomb_timer -= 1
        game_log(f"💣 Bomb Fuse Warning: {bomb_timer} ticks until core meltdown!", "#e67e22")
        if bomb_timer <= 0:
            game_log("\n💣💥 THE INTEGRATED MATRIX BOMB HAS EXPLODED. COMBAT EQUALIZED IN A DRAW.", "#ff0000")
            messagebox.showinfo("MATRIX DESTROYED", "The ticking payload detonated! Game Result: DRAW.")
            root.destroy()
            sys.exit()

    update_status_displays()
    check_game_over()

    if state["turn"] % 2 == 0:
        run_mutation_phase()
    else:
        state["turn"] += 1
        run_player_turn()

def apply_mutation(mutation, who):
    global bomb_timer
    game_log(f"⚡ {who.upper()} INJECTS OVERRIDE: {mutation}", "#ffcc00")

    if mutation == "ENABLE_TRIVIA": state["rules"]["trivia"] = True
    elif mutation == "ENABLE_GUNS": state["rules"]["guns_enabled"] = True
    elif mutation == "DISABLE_GUNS": state["rules"]["guns_enabled"] = False
    elif mutation == "DOUBLE_DAMAGE": state["rules"]["double_damage"] = True
    elif mutation == "HALF_DAMAGE": state["base_damage"] = max(1, state["base_damage"] // 2)
    elif mutation == "ADD_REGEN":
        state["rules"]["regen"] = True
        state["regen_value"] = 2
    elif mutation == "SUDDEN_DEATH":
        state["rules"]["sudden_death"] = True
        state["player_hp"] = min(state["player_hp"], 30)
        state["cpu_hp"] = min(state["cpu_hp"], 30)
    elif mutation == "INCREASE_PLAYER_HP": state["player_hp"] += 20
    elif mutation == "INCREASE_CPU_HP": state["cpu_hp"] += 20
    elif mutation == "DECREASE_PLAYER_HP": state["player_hp"] -= 10
    elif mutation == "DECREASE_CPU_HP": state["cpu_hp"] -= 10
    elif mutation == "INCREASE_BASE_DAMAGE": state["base_damage"] += 2
    elif mutation == "DECREASE_BASE_DAMAGE": state["base_damage"] = max(1, state["base_damage"] - 2)
    elif mutation == "REVERSE_DAMAGE": state["rules"]["reverse_damage"] = True
    elif mutation == "ENABLE_SHIELDS":
        state["player_defense"] += 2
        state["cpu_defense"] += 2
    elif mutation == "CRIT_BOOST": state["rules"]["crit_boost"] = True
    elif mutation == "CRIT_REDUCE": state["rules"]["crit_boost"] = False
    elif mutation == "SWAP_HP": state["player_hp"], state["cpu_hp"] = state["cpu_hp"], state["player_hp"]
    elif mutation == "STEAL_HP":
        if who == "player":
            state["player_hp"] += 10; state["cpu_hp"] -= 10
        else:
            state["cpu_hp"] += 10; state["player_hp"] -= 10
    elif mutation == "HP_EQUALISE":
        avg = (state["player_hp"] + state["cpu_hp"]) // 2
        state["player_hp"] = state["cpu_hp"] = avg
    elif mutation == "GLOBAL_DAMAGE_BOOST": state["base_damage"] += 3
    elif mutation == "GLOBAL_DAMAGE_REDUCE": state["base_damage"] = max(1, state["base_damage"] - 3)
    elif mutation == "RANDOM_DAMAGE_SPIKE": state["rules"]["random_damage_spike"] = True
    elif mutation == "LOW_HP_WIN": state["rules"]["low_hp_win"] = True
    elif mutation == "HIGH_HP_WIN": state["rules"]["high_hp_win"] = True
    elif mutation == "ENABLE_RPS": state["rules"]["rps_mode"] = True
    elif mutation == "BOMB_INSTALL":
        bomb_timer = random.randint(6, 15)
    elif mutation == "BOMB_ACCELERATE":
        if bomb_timer is not None: bomb_timer = max(1, bomb_timer - 3)
    elif mutation == "BOMB_SLOW":
        if bomb_timer is not None: bomb_timer += 3
    elif mutation == "INFUSE_POISON": state["rules"]["infuse_poison"] = True
    elif mutation == "INFUSE_BURN": state["rules"]["infuse_burn"] = True
    elif mutation == "INFUSE_SLEEP": state["rules"]["infuse_sleep"] = True
    elif mutation == "INFUSE_PARALYZE": state["rules"]["infuse_paralyze"] = True
    elif mutation == "INFUSE_FREEZE": state["rules"]["infuse_freeze"] = True
    elif mutation == "INFUSE_ACID": state["rules"]["infuse_acid"] = True
    elif mutation == "ENABLE_50_50": state["rules"]["fifty_fifty"] = True
    elif mutation == "DEFUSE_EFFECTS":
        for k in state["rules"]:
            if "infuse" in k: state["rules"][k] = False
    # ⚽ FOOTBALL SEASON LTM CARD EXECUTIONS
    elif mutation == "PENALTY_SHOOTOUT_LTM":
        # Fires the dialog game loop immediately when chosen/pulled
        play_penalty_shootout(who, "cpu" if who == "player" else "player")
        
    elif mutation == "RED_CARD_LTM":
        target = "cpu" if who == "player" else "player"
        # Accesses your status engine to bench (stun) the target for 2 rounds
        state["statuses"][target]["sleep"] = 2
        game_log(f"🟥 RED CARD! {target.upper()} committed a flagrant foul and is SENT OFF for 2 turns!", "#ff3333")
            
    update_status_displays()
    check_game_over()

def run_mutation_phase():
    global mutation_turn_toggle
    clear_action_space()
    game_log("\n⚡ ARENA MUTATION SEQUENCE ENGAGED ⚡", "#e056fd")
    
    first, second = ("player", "cpu") if mutation_turn_toggle else ("cpu", "player")
    mutation_turn_toggle = not mutation_turn_toggle
    
    def process_second_actor():
        if second == "player":
            render_player_mutation_cards(lambda: advance_round())
        else:
            cpu_choice = get_weighted_mutations(1)[0]
            apply_mutation(cpu_choice, "cpu")
            advance_round()

    def advance_round():
        state["turn"] += 1
        run_player_turn()

    if first == "player":
        render_player_mutation_cards(process_second_actor)
    else:
        cpu_choice = get_weighted_mutations(1)[0]
        apply_mutation(cpu_choice, "cpu")
        root.after(1000, process_second_actor)

def render_player_mutation_cards(next_step_callback):
    clear_action_space()
    game_log("🃏 Displaying available modifications inside structural UI frames...")
    
    rnd_options = get_weighted_mutations(5)
    available_cards = rnd_options + state["player_deck"]
    
    # Grid generation for mutation mechanics
    card_container = tk.Frame(action_area, bg="#121212")
    card_container.pack(expand=True, fill="both")
    
    def select_card(name):
        if name in state["player_deck"] and name not in rnd_options:
            state["player_deck"].remove(name)
        apply_mutation(name, "player")
        clear_action_space()
        next_step_callback()
        
    for mutation in available_cards:
        card = create_graphic_card(card_container, mutation, select_card)
        card.pack(side="left", padx=8, pady=10, expand=True)

# =========================
# INITIAL DRAFT CARD INTERFACE
# =========================

def execute_deck_draft_gui():
    """Builds a temporary fullscreen layout grid representing physical graphic cards for drafting."""
    draft_window = tk.Frame(root, bg="#121212")
    draft_window.place(relx=0, rely=0, relwidth=1, relheight=1)
    
    hdr = tk.Label(draft_window, text="🃏 DECK DRAFTING IN PROGRESS 🃏", font=("Courier", 20, "bold"), fg="#ffcc00", bg="#121212")
    hdr.pack(pady=20)
    
    sub = tk.Label(draft_window, text="Acquire 3 modification vectors to safeguard in reserve memory.", font=("Courier", 11), fg="#ffffff", bg="#121212")
    sub.pack(pady=5)
    
    counter_lbl = tk.Label(draft_window, text="Selected: 0 / 3", font=("Courier", 14), fg="#ffffff", bg="#121212")
    counter_lbl.pack(pady=10)
    
    scroll_canvas = tk.Canvas(draft_window, bg="#1c1c1c", highlightthickness=0)
    scrollbar = tk.Scrollbar(draft_window, orient="vertical", command=scroll_canvas.yview)
    grid_frame = tk.Frame(scroll_canvas, bg="#1c1c1c")
    
    grid_frame.bind("<Configure>", lambda e: scroll_canvas.configure(scrollregion=scroll_canvas.bbox("all")))
    scroll_canvas.create_window((0, 0), window=grid_frame, anchor="nw")
    scroll_canvas.configure(yscrollcommand=scrollbar.set)
    
    scroll_canvas.pack(side="left", fill="both", expand=True, padx=30, pady=10)
    scrollbar.pack(side="right", fill="y")
    
    all_muts = list(MUTATION_WEIGHTS.keys())
    
    def draft_pick(name):
        if len(state["player_deck"]) < 3:
            state["player_deck"].append(name)
            counter_lbl.config(text=f"Selected: {len(state['player_deck'])} / 3")
            game_log(f"✔️ Saved modification card: {name}")
            
            if len(state["player_deck"]) == 3:
                draft_window.destroy()
                initialize_battlefield_gui()

    # Populate grid with customized layout configurations
    cols = 4
    for index, mutation in enumerate(all_muts):
        r = index // cols
        c = index % cols
        card = create_graphic_card(grid_frame, mutation, draft_pick)
        card.grid(row=r, column=c, padx=15, pady=15)

# =========================
# GRAPHICAL LAYOUT INITIALIZATION
# =========================

def initialize_battlefield_gui():
    global player_panel, cpu_panel, p_hp_lbl, c_hp_lbl, turn_lbl, global_rules_lbl, rules_lbl, log_box, action_area
    
    # Top Control Status Banner
    hud = tk.Frame(root, bg="#1a1a1a", height=100, highlightbackground="#333333", highlightthickness=1)
    hud.pack(fill="x", side="top")
    hud.pack_propagate(False)
    
    turn_lbl = tk.Label(hud, text="ROUND 1", font=("Courier", 18, "bold"), fg="#ffcc00", bg="#1a1a1a")
    turn_lbl.pack(pady=5)
    
    global_rules_lbl = tk.Label(hud, text="", font=("Courier", 10), fg="#cccccc", bg="#1a1a1a")
    global_rules_lbl.pack()
    
    rules_lbl = tk.Label(hud, text="Global Mutations: None", font=("Courier", 10, "italic"), fg="#e056fd", bg="#1a1a1a")
    rules_lbl.pack(pady=2)

    # Core Combat Presentation Splitting Panels
    arena_view = tk.Frame(root, bg="#121212")
    arena_view.pack(fill="both", expand=True, pady=10)
    
    player_panel = tk.Frame(arena_view, bg="#1e272c", highlightbackground="#2a4d69", highlightthickness=3)
    player_panel.pack(side="left", expand=True, fill="both", padx=20, pady=10)
    
    p_name = tk.Label(player_panel, text="OPERATOR (PLAYER)", font=("Courier", 14, "bold"), fg="#4fc3f7", bg="#1e272c")
    p_name.pack(pady=10)
    p_hp_lbl = tk.Label(player_panel, text="HP: 100", font=("Courier", 22, "bold"), fg="#ffffff", bg="#1e272c")
    p_hp_lbl.pack(expand=True)

    cpu_panel = tk.Frame(arena_view, bg="#2c1e2b", highlightbackground="#4b2a4a", highlightthickness=3)
    cpu_panel.pack(side="right", expand=True, fill="both", padx=20, pady=10)
    
    c_name = tk.Label(cpu_panel, text="CENTRAL UNIT (CPU)", font=("Courier", 14, "bold"), fg="#f06292", bg="#2c1e2b")
    c_name.pack(pady=10)
    c_hp_lbl = tk.Label(cpu_panel, text="HP: 100", font=("Courier", 22, "bold"), fg="#ffffff", bg="#2c1e2b")
    c_hp_lbl.pack(expand=True)

    # Historical Action Output Logging Screen
    log_container = tk.Frame(root, bg="#1a1a1a", height=150)
    log_container.pack(fill="x", padx=20, pady=5)
    log_container.pack_propagate(False)
    
    log_box = tk.Text(log_container, bg="#0a0a0a", fg="#ffffff", font=("Courier", 10), state='disabled', wrap='word')
    log_box.pack(fill="both", expand=True)

    # Contextual Bottom Control Panel (Interactions/Cards get loaded inside here)
    action_area = tk.Frame(root, bg="#1a1a1a", height=220, highlightbackground="#333333", highlightthickness=1)
    action_area.pack(fill="x", side="bottom", padx=20, pady=10)
    action_area.pack_propagate(False)

    update_status_displays()
    check_updater_signals()
    run_player_turn()

# Run the app setup starting with drafting sequence
if __name__ == "__main__":
    execute_deck_draft_gui()
    root.mainloop()
