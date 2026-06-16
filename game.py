import threading
import time
import updater  # your updater module

running = True

def start_updater():
    updater.run_updater(lambda: running)

# start updater in background
threading.Thread(target=start_updater, daemon=True).start()

print("Game started")

try:
    while True:
        # YOUR GAME LOOP HERE
        time.sleep(1)

except KeyboardInterrupt:
    print("Game closing...")
    running = False



import random
import math
import sys

# =========================
# GAME STATE & WEIGHTS
# =========================

MUTATION_WEIGHTS = {
    # Standard Rules
    "ENABLE_GUNS": 10, "DISABLE_GUNS": 10, "DOUBLE_DAMAGE": 8, "HALF_DAMAGE": 8,
    "ENABLE_TRIVIA": 10, "ADD_REGEN": 10, "SUDDEN_DEATH": 2,
    
    # HP Manipulations
    "INCREASE_PLAYER_HP": 8, "INCREASE_CPU_HP": 8, "DECREASE_PLAYER_HP": 8, "DECREASE_CPU_HP": 8,
    "SWAP_HP": 2, "STEAL_HP": 4, "HP_EQUALISE": 3,
    
    # Stat Manipulations
    "INCREASE_BASE_DAMAGE": 10, "DECREASE_BASE_DAMAGE": 10, "ENABLE_SHIELDS": 10,
    "GLOBAL_DAMAGE_BOOST": 8, "GLOBAL_DAMAGE_REDUCE": 8, "CRIT_BOOST": 8, "CRIT_REDUCE": 8,
    
    # Chaos Rules
    "REVERSE_DAMAGE": 4, "RANDOM_DAMAGE_SPIKE": 5, "LOW_HP_WIN": 1, "HIGH_HP_WIN": 1,
    "BOMB_INSTALL": 5, "BOMB_ACCELERATE": 5, "BOMB_SLOW": 5, "ENABLE_RPS": 4,
    
    # Status Infusions
    "INFUSE_POISON": 8, "INFUSE_BURN": 8, "INFUSE_SLEEP": 6, "INFUSE_PARALYZE": 6, "INFUSE_FREEZE": 5,
    
    # New Rules
    "INFUSE_ACID": 7,
    "ENABLE_50_50": 2,
    "DEFUSE_EFFECTS": 3
}

state = {
    "player_hp": 100,
    "cpu_hp": 100,
    "base_damage": 5,
    "player_defense": 0,
    "cpu_defense": 0,
    "turn": 1,
    "player_deck": [],
    
    "statuses": {
        "player": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False},
        "cpu": {"poison": 0, "burn": 0, "sleep": 0, "paralyze": False, "freeze": False}
    },

    "rules": {
        "guns_enabled": False,
        "trivia": False,
        "double_damage": False,
        "regen": False,
        "sudden_death": False,
        "reverse_damage": False,
        "random_damage_spike": False,
        "crit_boost": False,
        "low_hp_win": False,
        "high_hp_win": False,
        "rps_mode": False,
        
        # Status effect toggles
        "infuse_poison": False,
        "infuse_burn": False,
        "infuse_sleep": False,
        "infuse_paralyze": False,
        "infuse_freeze": False,
        "infuse_acid": False,
        
        # Chaos toggles
        "fifty_fifty": False
    },
    "regen_value": 0
}

# =========================
# UTILITIES
# =========================

def get_weighted_mutations(k):
    """Returns k unique mutations based on their weights."""
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

def draft_deck():
    """Allows the player to draft 3 mutations for their hand."""
    print("\n" + "="*40)
    print("      🃏 DRAFT YOUR DECK 🃏      ")
    print("="*40)
    print("Choose 3 Mutations to keep in your hand.")
    print("They bypass RNG and can be played ONCE during your mutation phase.\n")
    
    all_muts = list(MUTATION_WEIGHTS.keys())
    for i in range(0, len(all_muts), 3):
        row = all_muts[i:i+3]
        print("".join(f"{item:<25}" for item in row))
        
    print("\nType the EXACT name of the mutation you want.")
    
    while len(state["player_deck"]) < 3:
        choice = input(f"Draft Card {len(state['player_deck']) + 1}/3 > ").strip()
        if choice in all_muts:
            state["player_deck"].append(choice)
            print(f"✔️ Added {choice} to your deck.")
        else:
            print("❌ Invalid selection. Check spelling.")
    print("\nDeck drafted! Let the game begin...")

# =========================
# SYSTEMS (Trivia, Bomb, Check Win)
# =========================

TRIVIA = [
    {"q": "What is 2 + 2?", "a": "4"},
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "What planet do we live on?", "a": "earth"},
    {"q": "What is 10 / 2?", "a": "5"},
    {"q": "What colour is the sky on a clear day?", "a": "blue"}
]

bomb_timer = None

def try_trivia(attacker):
    if not state["rules"]["trivia"]: return "pass"
    if random.random() > 0.25: return "pass"

    q = random.choice(TRIVIA)
    print(f"\n❓ TRIVIA FOR {attacker.upper()}!")
    print(q["q"])

    if attacker == "cpu":
        ans = q["a"] if random.random() > 0.5 else "wrong_answer"
        print(f"> {ans}")
    else:
        ans = input("> ").strip().lower()

    if ans == q["a"]:
        print("✔ Correct!")
        return "correct"
    else:
        print("✖ Wrong!")
        return "wrong"

def maybe_explode_bomb():
    global bomb_timer
    if bomb_timer is None: return

    bomb_timer -= 1
    print(f"💣 Bomb Timer: {bomb_timer} turns remaining...")

    if bomb_timer <= 0:
        print("\n💣💥 THE BOMB DETONATED! IT'S A DRAW.")
        sys.exit()

def check_game_over():
    p_dead = state["player_hp"] <= 0
    c_dead = state["cpu_hp"] <= 0

    if p_dead or c_dead:
        print("\n====================")
        print("     GAME OVER      ")
        print(f"Final Player HP: {state['player_hp']} | CPU HP: {state['cpu_hp']}")
        print("====================")
        
        if state["rules"]["low_hp_win"]:
            print("📜 'LOW HP WIN' condition is active!")
            if state["player_hp"] < state["cpu_hp"]: print("PLAYER WINS (Lowest HP)!")
            elif state["cpu_hp"] < state["player_hp"]: print("CPU WINS (Lowest HP)!")
            else: print("DRAW!")
            sys.exit()

        if state["rules"]["high_hp_win"]:
            print("📜 'HIGH HP WIN' condition is active!")
            if state["player_hp"] > state["cpu_hp"]: print("PLAYER WINS (Highest HP)!")
            elif state["cpu_hp"] > state["player_hp"]: print("CPU WINS (Highest HP)!")
            else: print("DRAW!")
            sys.exit()

        if p_dead and c_dead: print("MUTUAL DESTRUCTION - DRAW!")
        elif p_dead: print("CPU WINS!")
        else: print("PLAYER WINS!")
        sys.exit()

# =========================
# STATUS EFFECTS & RPS
# =========================

def apply_status(defender):
    """Rolls to apply active infused statuses on hit."""
    chance = 0.3 # 30% chance to apply
    if state["rules"]["infuse_poison"] and random.random() < chance:
        state["statuses"][defender]["poison"] += 3
        print(f"🍄 {defender.upper()} was Poisoned for 3 turns!")
        
    if state["rules"]["infuse_burn"] and random.random() < chance:
        state["statuses"][defender]["burn"] += 3
        print(f"🔥 {defender.upper()} was Burned for 3 turns!")
        
    if state["rules"]["infuse_sleep"] and random.random() < chance:
        state["statuses"][defender]["sleep"] = random.randint(1, 2)
        print(f"💤 {defender.upper()} fell asleep!")
        
    if state["rules"]["infuse_paralyze"] and random.random() < chance:
        state["statuses"][defender]["paralyze"] = True
        print(f"⚡ {defender.upper()} is Paralyzed!")
        
    if state["rules"]["infuse_freeze"] and random.random() < chance:
        state["statuses"][defender]["freeze"] = True
        print(f"🧊 {defender.upper()} was Frozen solid!")

    if state["rules"]["infuse_acid"] and random.random() < chance:
        state["statuses"][defender]["poison"] += 1  # Acid acts as a short, intense 1-turn poison
        print(f"🧪 {defender.upper()} was splashed with Acid! (1 turn of Poison applied)")

def check_can_act(actor):
    """Checks paralyze, sleep, and freeze before allowing a turn."""
    s = state["statuses"][actor]
    
    if s["sleep"] > 0:
        print(f"💤 {actor.upper()} is fast asleep...")
        s["sleep"] -= 1
        return False
        
    if s["freeze"]:
        if random.random() < 0.25:
            print(f"🧊✨ {actor.upper()} thawed out!")
            s["freeze"] = False
        else:
            print(f"🧊 {actor.upper()} is frozen solid!")
            return False
            
    if s["paralyze"]:
        if random.random() < 0.25:
            print(f"⚡ {actor.upper()} is fully paralyzed and cannot move!")
            return False
            
    return True

def apply_end_of_turn_status():
    """Applies poison and burn damage at the end of the round."""
    for actor in ["player", "cpu"]:
        s = state["statuses"][actor]
        
        if s["poison"] > 0:
            print(f"🍄 {actor.upper()} takes 5 Poison damage.")
            state[f"{actor}_hp"] -= 5
            s["poison"] -= 1
            
        if s["burn"] > 0:
            print(f"🔥 {actor.upper()} takes 3 Burn damage.")
            state[f"{actor}_hp"] -= 3
            s["burn"] -= 1
            
    check_game_over()

def play_rps(attacker, defender):
    """Replaces normal combat when RPS mode is active."""
    print(f"\n✂️ 📄 🪨 {attacker.upper()}'s RPS ATTACK!")
    opts = ["rock", "paper", "scissors"]
    
    if attacker == "player":
        choice = input("Choose rock, paper, or scissors: > ").strip().lower()
        while choice not in opts: choice = input("> ").strip().lower()
        cpu_choice = random.choice(opts)
        def_choice = cpu_choice
    else:
        choice = random.choice(opts)
        def_choice = input("CPU is attacking! Defend with rock, paper, or scissors: > ").strip().lower()
        while def_choice not in opts: def_choice = input("> ").strip().lower()

    print(f"{attacker.upper()} plays {choice.upper()}! {defender.upper()} plays {def_choice.upper()}!")
    
    win_conditions = {"rock": "scissors", "paper": "rock", "scissors": "paper"}
    
    if choice == def_choice:
        print("🤝 It's a Tie! No damage dealt.")
    elif win_conditions[choice] == def_choice:
        dmg = state["base_damage"] * 3
        print(f"🎯 {attacker.upper()} WINS! Deals {dmg} massive damage!")
        state[f"{defender}_hp"] -= dmg
    else:
        print(f"🛡️ {defender.upper()} WINS the counter! Attack deflected!")
        
    check_game_over()

# =========================
# COMBAT
# =========================

def attack(attacker, defender):
    # Overriding system: 50/50 Coin Flip Instant End
    if state["rules"]["fifty_fifty"]:
        print("\n🎲 50/50 ACTIVE — PURE COIN FLIP")
        winner = random.choice(["player", "cpu"])
        loser = "cpu" if winner == "player" else "player"

        state[f"{loser}_hp"] = 0
        print(f"🏆 {winner.upper()} WINS INSTANTLY")
        check_game_over()
        return

    if state["rules"]["rps_mode"]:
        play_rps(attacker, defender)
        return

    base = state["base_damage"]
    damage = base

    # Burn Penalty
    if state["statuses"][attacker]["burn"] > 0:
        damage = max(1, damage // 2)

    if state["rules"]["guns_enabled"]:
        damage += 10
        print("💥 Guns are blazing!")

    if state["rules"]["double_damage"]: damage *= 2
    if state["rules"]["sudden_death"]: damage *= 3
    if state["rules"]["random_damage_spike"]: damage *= random.randint(1, 4)
    if state["rules"]["crit_boost"] and random.random() < 0.4:
        print("✨ CRITICAL HIT!")
        damage *= 2

    result = try_trivia(attacker)
    if result == "correct":
        damage *= 2
        print("🔥 Trivia boost!")
    elif result == "wrong":
        damage = max(1, damage // 2)
        print("💀 Trivia penalty")

    damage = int(damage)
    defense = state["player_defense"] if defender == "player" else state["cpu_defense"]
    
    if state["rules"]["reverse_damage"]:
        actual_change = -damage 
        print(f"❤️ Reverse Damage active! {defender.upper()} absorbs the energy.")
    else:
        actual_change = max(0, damage - defense)

    if defender == "player": state["player_hp"] -= actual_change
    else: state["cpu_hp"] -= actual_change

    print(f"⚔️ {attacker.upper()} strikes! Balance shifts by {actual_change} points on {defender.upper()}.")
    apply_status(defender)
    check_game_over()

def turn(actor):
    if not check_can_act(actor):
        return
    if actor == "player": attack("player", "cpu")
    else: attack("cpu", "player")

# =========================
# MUTATION ENGINE
# =========================

def apply_mutation(mutation, who):
    global bomb_timer
    print(f"\n⚡ {who.upper()} triggers {mutation}")

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
        print("💣 A countdown bomb has been installed!")
    elif mutation == "BOMB_ACCELERATE":
        if bomb_timer is not None:
            bomb_timer = max(1, bomb_timer - 3)
            print("💣 The bomb countdown accelerates!")
    elif mutation == "BOMB_SLOW":
        if bomb_timer is not None:
            bomb_timer += 3
            print("💣 The bomb countdown delays...")
            
    # Status Toggles
    elif mutation == "INFUSE_POISON": state["rules"]["infuse_poison"] = True
    elif mutation == "INFUSE_BURN": state["rules"]["infuse_burn"] = True
    elif mutation == "INFUSE_SLEEP": state["rules"]["infuse_sleep"] = True
    elif mutation == "INFUSE_PARALYZE": state["rules"]["infuse_paralyze"] = True
    elif mutation == "INFUSE_FREEZE": state["rules"]["infuse_freeze"] = True
    
    # Newly Integrated Rule Mutations
    elif mutation == "INFUSE_ACID": state["rules"]["infuse_acid"] = True
    elif mutation == "ENABLE_50_50": state["rules"]["fifty_fifty"] = True
    elif mutation == "DEFUSE_EFFECTS":
        for k in state["rules"]:
            if "infuse" in k:
                state["rules"][k] = False
        print("🧯 All infused effects removed!")
            
    check_game_over()

# =========================
# GAME LOOP
# =========================

draft_deck()
mutation_turn_toggle = True

while True:
    print("\n" + "="*30)
    print(f"TURN {state['turn']}")
    print(f"Player HP: {state['player_hp']} | CPU HP: {state['cpu_hp']}")
    print(f"Base Dmg: {state['base_damage']} | Shield P/C: {state['player_defense']}/{state['cpu_defense']}")
    print("="*30)

    # 1. Player Turn
    turn("player")
    
    # 2. CPU Turn
    turn("cpu")

    # 3. Upkeep / Regeneration Phase
    apply_end_of_turn_status()
    
    if state["rules"]["regen"]:
        state["player_hp"] += state["regen_value"]
        state["cpu_hp"] += state["regen_value"]
        print(f"⏳ Regeneration (+{state['regen_value']} HP)")

    maybe_explode_bomb()

    # 4. Mutation Phase
    if state["turn"] % 2 == 0:
        print("\n⚡ MUTATION PHASE ⚡")

        first, second = ("player", "cpu") if mutation_turn_toggle else ("cpu", "player")
        mutation_turn_toggle = not mutation_turn_toggle

        for active_actor in [first, second]:
            if active_actor == "player":
                rnd_options = get_weighted_mutations(5)
                print(f"\n🎲 RNG Mutations: {rnd_options}")
                if state["player_deck"]:
                    print(f"🃏 Deck Mutations: {state['player_deck']}")
                
                valid_choices = rnd_options + state["player_deck"]
                choice = input("> Choose a Mutation: ").strip()
                
                while choice not in valid_choices:
                    print(f"❌ Invalid selection. Choose from the available options.")
                    choice = input("> ").strip()
                    
                # Consume deck card if played
                if choice in state["player_deck"] and choice not in rnd_options:
                    state["player_deck"].remove(choice)
                    
            else:
                choice = get_weighted_mutations(1)[0]

            apply_mutation(choice, active_actor)

    state["turn"] += 1
