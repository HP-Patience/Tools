import json
import math
import sys
from pathlib import Path


SIGILS = {
    "piercing_ember",
    "ash_crown",
    "sacred_nail",
    "light_ember",
    "rekindle",
    "wide_radiance",
    "close_flame",
    "last_candle",
    "blood_prayer",
}
SIGIL_CATEGORIES = {
    "piercing_ember": "projectile",
    "ash_crown": "projectile",
    "sacred_nail": "projectile",
    "light_ember": "survival",
    "rekindle": "survival",
    "wide_radiance": "survival",
    "close_flame": "risk",
    "last_candle": "risk",
    "blood_prayer": "risk",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def close(actual, expected, tolerance=0.01):
    return isinstance(actual, (int, float)) and math.isclose(
        actual, expected, abs_tol=tolerance
    )


def load_trace(path):
    snapshots = []
    decoder = json.JSONDecoder()
    raw = Path(path).read_text(encoding="utf-8")
    index = 0
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw):
            break
        value, index = decoder.raw_decode(raw, index)
        if isinstance(value, dict) and "nodes" in value:
            snapshots.append(value)
    require(snapshots, f"no runtime snapshots found in {path}")
    return snapshots


def runtimes(snapshot):
    return [
        node["runtime"]
        for node in snapshot.get("nodes", {}).values()
        if isinstance(node.get("runtime"), dict)
    ]


def node_entries(snapshot):
    return [
        (node_id, node, node.get("runtime", {}))
        for node_id, node in snapshot.get("nodes", {}).items()
        if isinstance(node.get("runtime"), dict)
    ]


def nodes_with(snapshot, field, value=None):
    matches = [entry for entry in node_entries(snapshot) if field in entry[2]]
    if value is not None:
        matches = [entry for entry in matches if entry[2].get(field) == value]
    return matches


def node_position(entry):
    transform = entry[1].get("transform", {})
    runtime_position = entry[2].get("position", {})
    return {
        "x": transform.get("x", runtime_position.get("x")),
        "y": transform.get("y", runtime_position.get("y")),
    }


def distance(a, b):
    pa, pb = node_position(a), node_position(b)
    require(all(isinstance(p.get(axis), (int, float)) for p in (pa, pb) for axis in ("x", "y")), "node position missing")
    return math.hypot(pa["x"] - pb["x"], pa["y"] - pb["y"])


def node_by_attack(snapshot, attack_id):
    matches = nodes_with(snapshot, "attackId", attack_id)
    require(matches, f"attack node {attack_id!r} missing")
    return matches[0]


def compressed(values):
    result = []
    for value in values:
        if value is not None and (not result or result[-1] != value):
            result.append(value)
    return result


def contains_subsequence(values, expected):
    index = 0
    for value in values:
        if index < len(expected) and value == expected[index]:
            index += 1
    return index == len(expected)


def with_field(snapshot, field):
    return [runtime for runtime in runtimes(snapshot) if field in runtime]


def one(snapshot, field):
    matches = with_field(snapshot, field)
    require(matches, f"runtime field {field!r} is missing")
    return matches[0]


def director(snapshot):
    return one(snapshot, "runState")


def player(snapshot):
    matches = [state for state in runtimes(snapshot) if "skill" in state and "hp" in state]
    require(matches, "PlayerController runtime state is missing")
    return matches[0]


def combat_input(snapshot):
    return one(snapshot, "heldActions")


def room(snapshot):
    return one(snapshot, "doorsClosed")


def enemies(snapshot, kind=None):
    matches = [state for state in runtimes(snapshot) if "kind" in state]
    if kind is not None:
        matches = [state for state in matches if state.get("kind") == kind]
    return matches


def projectiles(snapshot, side=None):
    matches = [state for state in runtimes(snapshot) if "ownerSide" in state]
    if side is not None:
        matches = [state for state in matches if state.get("ownerSide") == side]
    return matches


def areas(snapshot):
    return [
        state
        for state in runtimes(snapshot)
        if "phase" in state and "hitPlayer" in state
    ]


def action_active(action_state, action):
    value = action_state.get(action) if isinstance(action_state, dict) else None
    if isinstance(value, dict):
        return any(value.get(key) is True for key in ("held", "pressed", "active"))
    return value is True


def assert_run_start(s):
    require(len(s) >= 70, "run-start trace must sample the title transition frame-by-frame")
    first_combat_index = next(
        (index for index, snap in enumerate(s) if director(snap).get("runState") == "combat"),
        None,
    )
    require(first_combat_index is not None and first_combat_index > 1, "title never transitioned to combat")
    require(
        all(director(snap).get("runState") == "title" for snap in s[:first_combat_index]),
        "non-title state appeared before the first combat frame",
    )
    before = s[0]
    locked = s[min(10, first_combat_index - 1)]
    combat = s[first_combat_index]
    require(director(before).get("runState") == "title", "fresh run must begin at title")
    require(director(locked).get("runState") == "title", "title must still own early frames")
    require(player(before).get("position") == player(locked).get("position") and player(locked).get("firing") is False, "title allowed player movement/fire")
    before_enemies = [(e.get("kind"), e.get("behaviorState"), e.get("attackId")) for e in enemies(before)]
    locked_enemies = [(e.get("kind"), e.get("behaviorState"), e.get("attackId")) for e in enemies(locked)]
    require(before_enemies == locked_enemies, "title allowed enemy AI to advance")
    require(not projectiles(locked) and not areas(locked), "title created combat damage nodes")
    run = director(combat)
    hero = player(combat)
    require(run.get("runState") == "combat" and run.get("stage") == 1, "Stage 1 combat missing")
    require(run.get("roomName") == "熄火门廊" and run.get("layoutId") == "open-vestibule", "Stage 1 room identity mismatch")
    require(run.get("enemyCount") == 2, "Stage 1 must contain exactly two enemies")
    require(run.get("damagingObjectCount") == 0, "first Stage 1 combat frame must contain no damaging objects")
    require(run.get("ownedSigils") == [], "fresh run must own no sigils")
    require(run.get("exitOpen") is False and room(combat).get("doorsClosed") is True, "exit must be closed")
    require(len(enemies(combat, "shadow_fang")) == 2, "Stage 1 roster must be two Shadow Fangs")
    require((hero.get("hp"), hero.get("maxHp")) == (100, 100), "base HP must be 100/100")
    require((hero.get("shotDamage"), hero.get("shotsPerSecond")) == (20, 3), "base shot stats mismatch")
    require(close(hero.get("movementSpeed"), 260), "base movement speed must be 260")
    require(hero.get("skill", {}).get("ready") is True, "Pureflame Pulse must start ready")
    require(not enemies(combat, "fallen_bishop") and one(combat, "bossBarVisible").get("bossBarVisible") is False, "Boss/Boss bar present outside Stage 7")


def assert_input_edges(s):
    require(len(s) == 9, "input-edge trace must contain pointer leave/return, blur/focus, and modal suppression phases")
    pointer_held, pointer_left, pointer_return, move_held, blurred, focused, suppressed, suppressed_return, released = s
    require("fire" in combat_input(pointer_held).get("heldActions", []) and player(pointer_held).get("firing") is True, "pointer fire never became held")
    require("fire" not in combat_input(pointer_left).get("heldActions", []) and player(pointer_left).get("firing") is False, "pointer leave did not clear fire")
    require(combat_input(pointer_left).get("aim") == combat_input(pointer_held).get("aim"), "pointer leave did not retain last valid aim")
    require("fire" not in combat_input(pointer_return).get("heldActions", []) and player(pointer_return).get("firing") is False, "pointer return resumed fire without a fresh press")
    old_ids = {p.get("attackId") for p in projectiles(pointer_left, "player")}
    return_ids = {p.get("attackId") for p in projectiles(pointer_return, "player")}
    require(return_ids <= old_ids, "pointer return spawned a new projectile without fresh press")

    require({"move_right", "fire"}.issubset(set(combat_input(move_held).get("heldActions", []))), "blur setup did not hold movement and fire")
    require(not combat_input(blurred).get("heldActions") and player(blurred).get("firing") is False, "window blur did not clear held movement/fire")
    require(not combat_input(focused).get("heldActions") and player(focused).get("firing") is False, "focus return restored held input")
    require(combat_input(suppressed).get("pointerFireSuppressed") is True and player(suppressed).get("firing") is False, "modal close did not suppress held pointer")
    require(combat_input(suppressed_return).get("pointerFireSuppressed") is True and player(suppressed_return).get("firing") is False, "pointer movement cleared modal suppression before release")
    require(combat_input(released).get("pointerFireSuppressed") is False and player(released).get("firing") is False, "pointer release did not clear suppression cleanly")


def assert_projectiles(s):
    require(len(s) == 10, "projectile trace must contain exactly ten scenario snapshots")
    straight_a, straight_b, wall_a, wall_b, base_before, base_after, pierce_before, pierce_one, pierce_two, pierce_end = s

    bolt_a = nodes_with(straight_a, "ownerSide", "player")
    bolt_b = nodes_with(straight_b, "ownerSide", "player")
    require(len(bolt_a) == len(bolt_b) == 1, "straight-flight scenario needs one persistent bolt")
    require(bolt_a[0][2].get("attackId") == bolt_b[0][2].get("attackId"), "straight-flight bolt identity changed")
    pa, pb = node_position(bolt_a[0]), node_position(bolt_b[0])
    require(pb["x"] > pa["x"] and close(pb["y"], pa["y"], 0.5), "Ember Bolt did not travel in a straight line")
    require(bolt_a[0][2].get("damage") == 20 and isinstance(bolt_a[0][2].get("damage"), int), "base bolt damage must be integer 20")

    wall_bolts = nodes_with(wall_a, "ownerSide", "player")
    require(len(wall_bolts) == 1, "wall scenario did not spawn a bolt")
    wall_id = wall_bolts[0][2].get("attackId")
    require(not nodes_with(wall_b, "attackId", wall_id), "solid wall failed to destroy/block player projectile")
    require([e.get("hp") for e in enemies(wall_a)] == [e.get("hp") for e in enemies(wall_b)], "wall-blocked bolt damaged an enemy")

    hp_order = lambda snap: [
        entry[2].get("hp")
        for entry in sorted(
            [
                entry
                for entry in node_entries(snap)
                if entry[1].get("enabled") is not False
                and "enemy" in entry[1].get("tags", [])
            ],
            key=lambda entry: node_position(entry)["x"],
        )
    ]
    require(hp_order(base_before) == [60, 60], "base first-hit setup mismatch")
    require(hp_order(base_after) == [40, 60], "base bolt did not stop after exactly the first enemy")
    require(not projectiles(base_after, "player"), "base bolt survived its first enemy hit")

    require(hp_order(pierce_before) == [60, 60, 60], "piercing setup mismatch")
    piercing_samples = [pierce_one, pierce_two, pierce_end]
    first_hit = next(
        (snap for snap in piercing_samples if hp_order(snap) == [44, 60, 60]),
        None,
    )
    require(first_hit is not None, "piercing bolt first hit/damage mismatch")
    piercing_bolts = projectiles(first_hit, "player")
    require(len(piercing_bolts) == 1 and piercing_bolts[0].get("pierceRemaining") == 0, "piercing bolt did not spend exactly one extra penetration")
    require(
        any(hp_order(snap) == [44, 44, 60] for snap in piercing_samples),
        "piercing bolt did not hit exactly one additional enemy",
    )
    require(hp_order(pierce_end) == [44, 44, 60] and not projectiles(pierce_end, "player"), "piercing bolt reached a forbidden third enemy")


def assert_pureflame_pulse(s):
    require(len(s) == 3, "pulse trace must contain before, immediate-after, and post-hit snapshots")
    before, used, damaged = s
    player_before = nodes_with(before, "skill")[0]
    player_used = nodes_with(used, "skill")[0]
    p0, p1, p2 = player(before), player(used), player(damaged)
    inner = node_by_attack(before, "pulse-inner")
    outer = node_by_attack(before, "pulse-outer")
    require(distance(player_before, inner) < 150, "inner hostile projectile was not inside base pulse radius")
    require(distance(player_before, outer) > 150, "outer hostile projectile was not outside base pulse radius")
    require(not nodes_with(used, "attackId", "pulse-inner"), "pulse failed to remove inside hostile projectile")
    require(nodes_with(used, "attackId", "pulse-outer"), "pulse incorrectly removed outside hostile projectile")

    fang0 = nodes_with(before, "kind", "shadow_fang")[0]
    fang1 = nodes_with(used, "kind", "shadow_fang")[0]
    require(fang0[2].get("behaviorState") == "charge", "ordinary enemy was not deterministically charging")
    require(fang1[2].get("behaviorState") == "recover", "pulse did not interrupt ordinary charge into recovery")
    require(distance(player_before, fang1) > distance(player_before, fang0), "pulse did not push ordinary enemy away")
    require(close(distance(fang0, fang1), 128, 2), "ordinary enemy Pulse knockback was not 128px")
    require(fang1[2].get("hp") == fang0[2].get("hp"), "pulse dealt forbidden damage")
    require(nodes_with(damaged, "kind", "shadow_fang")[0][2].get("behaviorState") == "recover", "interrupted enemy skipped required recovery window")

    for kind in ("dusk_deacon", "fallen_bishop"):
        elite0 = nodes_with(before, "kind", kind)[0]
        elite1 = nodes_with(used, "kind", kind)[0]
        require(node_position(elite1) == node_position(elite0), f"pulse moved {kind}")
        require(elite1[2].get("behaviorState") == elite0[2].get("behaviorState"), f"pulse interrupted {kind}")

    hazard0 = node_by_attack(before, "pulse-hazard")
    hazard1 = node_by_attack(used, "pulse-hazard")
    require(hazard1[2].get("phase") == hazard0[2].get("phase"), "pulse altered ground hazard")
    require(p1.get("hp") == p0.get("hp") and node_position(player_used) == node_position(player_before), "pulse changed player HP or position")
    require(p1.get("skill", {}).get("ready") is False and p1.get("skill", {}).get("cooldownRemaining", 0) > 0, "pulse cooldown missing")
    require(p2.get("hp") == p1.get("hp") - 15, "player could not take normal damage after pulse; immunity may be active")
    require(not nodes_with(damaged, "attackId", "pulse-outer"), "post-pulse projectile did not resolve on player")


def assert_skill_edges(s):
    require(len(s) == 8, "skill-edge trace needs cooldown, paused cooldown, paused buff, and rejection snapshots")
    used, repeated, paused_a, paused_b, resumed, buff_a, buff_b, rejected = s
    u, r = player(used), player(repeated)
    require(r.get("hp") == u.get("hp"), "cooldown press changed HP")
    elapsed = (repeated.get("frame", 0) - used.get("frame", 0)) / 60
    cooldown_delta = u.get("skill", {}).get("cooldownRemaining", 0) - r.get("skill", {}).get("cooldownRemaining", 0)
    require(abs(cooldown_delta - elapsed) <= 0.06, "cooldown press restarted or altered cooldown")
    require(u.get("skill", {}).get("buffRemaining", 0) == r.get("skill", {}).get("buffRemaining", 0), "cooldown press changed buff")
    require(len(projectiles(used)) == len(projectiles(repeated)) and len(enemies(used)) == len(enemies(repeated)), "cooldown press changed combat nodes")
    a = player(paused_a).get("skill", {})
    b = player(paused_b).get("skill", {})
    require(close(a.get("cooldownRemaining"), b.get("cooldownRemaining"), 0.03), "pause advanced cooldown")
    require(player(paused_a).get("position") == player(paused_b).get("position"), "pause advanced player physics")
    require([(p.get("attackId"), p.get("hitRegistered")) for p in projectiles(paused_a)] == [(p.get("attackId"), p.get("hitRegistered")) for p in projectiles(paused_b)], "pause advanced projectile state")
    require([(e.get("kind"), e.get("behaviorState"), e.get("attackId")) for e in enemies(paused_a)] == [(e.get("kind"), e.get("behaviorState"), e.get("attackId")) for e in enemies(paused_b)], "pause advanced enemy timers/state")
    require(player(resumed).get("skill", {}).get("cooldownRemaining") < b.get("cooldownRemaining"), "resume did not advance cooldown")
    buff_start = player(buff_a).get("skill", {})
    buff_end = player(buff_b).get("skill", {})
    require(buff_start.get("buffRemaining", 0) > 0, "Blood Prayer buff setup missing")
    require(close(buff_start.get("buffRemaining"), buff_end.get("buffRemaining"), 0.03), "pause advanced Blood Prayer buff timer")
    require(close(buff_start.get("cooldownRemaining"), buff_end.get("cooldownRemaining"), 0.03), "pause advanced Blood Prayer cooldown")
    rejected_player = player(rejected)
    require(rejected_player.get("hp") == 8, "Blood Prayer rejection changed HP")
    rejected_skill = rejected_player.get("skill", {})
    require(rejected_skill.get("lastRejected") not in (None, False, ""), "Blood Prayer low-HP rejection missing")
    require(rejected_skill.get("cooldownRemaining", 0) <= 0, "rejected skill began cooldown")
    require(rejected_skill.get("buffRemaining", 0) <= 0 and not projectiles(rejected), "rejected skill created buff/projectile side effects")
    require(one(rejected, "skillState").get("skillState") == "rejected", "HUD did not communicate Blood Prayer rejection")


def assert_damage_resolution(s):
    require(len(s) == 7, "damage trace must contain contact, dedup, clamp, and two mutual-death scenarios")
    contact_before, contact_after, repeated, distinct, clamped, ordinary_mutual, elite_mutual = s
    require(player(contact_before).get("hp") == player(contact_after).get("hp") == 100, "body contact caused damage")
    require(player(repeated).get("hp") == 80, "same attackId damaged more than once")
    require(player(distinct).get("hp") == 60, "distinct attack did not apply independently")
    require(player(clamped).get("hp") == 0, "overkill HP was not clamped to zero")
    for snap, label in ((ordinary_mutual, "ordinary"), (elite_mutual, "elite")):
        run = director(snap)
        require(run.get("result", {}).get("outcome") == "lose", f"{label} mutual death did not prioritize Lose")
        require(run.get("result", {}).get("remainingHp") == 0, f"{label} Lose result HP mismatch")
        require(run.get("runState") in {"death-presentation", "death"}, f"{label} mutual death did not enter death flow")
        require(run.get("offeredSigils") == [], f"{label} mutual death granted a sigil reward")
    require(player(elite_mutual).get("hp") == 0, "Elite mutual death incorrectly applied 10-HP heal")


def assert_enemy_behaviors(s):
    def samples(kind, excluded_attack=None):
        result = []
        for snap in s:
            matches = nodes_with(snap, "kind", kind)
            if len(matches) == 1 and (
                excluded_attack is None
                or matches[0][2].get("attackId") != excluded_attack
            ):
                result.append((snap.get("frame"), matches[0]))
        return result

    fang = samples("shadow_fang")
    acolyte = samples("shadow_acolyte")
    deacon = samples("dusk_deacon", "elite-pulse")
    require(fang and acolyte and deacon, "each enemy kind needs an isolated behavior trace")
    fang_states = compressed(entry[1][2].get("behaviorState") for entry in fang)
    acolyte_states = compressed(entry[1][2].get("behaviorState") for entry in acolyte)
    deacon_states = compressed(entry[1][2].get("behaviorState") for entry in deacon)
    require(contains_subsequence(fang_states, ["approach", "charge", "strike", "recover", "approach"]), f"Fang state order invalid: {fang_states}")
    require(contains_subsequence(acolyte_states, ["move", "charge", "release", "recover", "move"]), f"Acolyte state order invalid: {acolyte_states}")
    melee = ["approach", "melee-charge", "active", "recover", "approach"]
    ranged = ["approach", "ranged-charge", "active", "recover", "approach"]
    require(contains_subsequence(deacon_states, melee) or contains_subsequence(deacon_states, ranged), f"Deacon committed state order invalid: {deacon_states}")

    commits = []
    previous_count = -1
    for frame, entry in acolyte:
        state = entry[2]
        count = state.get("attackCommitCount")
        require(isinstance(count, int), "Acolyte attackCommitCount is missing")
        if count > previous_count:
            commits.append((frame, count, state.get("attackCommitTime"), state.get("lastAttackCommitInterval"), state.get("attackId")))
            previous_count = count
    committed = [entry for entry in commits if entry[1] > 0]
    require(len(committed) >= 2 and committed[-1][1] >= 2, "Acolyte trace must include at least two attack commits")
    require(all(isinstance(entry[2], (int, float)) for entry in committed), "Acolyte attackCommitTime is missing")
    require(all(b[2] > a[2] for a, b in zip(committed, committed[1:])), "Acolyte attackCommitTime did not increase")
    require(isinstance(committed[-1][3], (int, float)) and committed[-1][3] >= 1.8, "Acolyte lastAttackCommitInterval was below 1.8 seconds")

    committed_ids = [entry[4] for entry in committed if entry[4]]
    require(len(committed_ids) >= 2, "Acolyte commit attackId is missing")
    release_frames = {}
    for frame, entry in acolyte:
        state = entry[2]
        if state.get("behaviorState") == "release" and state.get("attackId"):
            release_frames.setdefault(state.get("attackId"), frame)
    commit_frames = {entry[4]: entry[0] for entry in committed if entry[4]}
    require(
        all(attack_id in commit_frames and commit_frames[attack_id] < frame for attack_id, frame in release_frames.items()),
        "Acolyte release appeared without a prior matching commit",
    )
    released_ids = set(release_frames)
    covered_ids = [attack_id for attack_id in committed_ids if attack_id in released_ids]
    require(len(covered_ids) >= 2, "Acolyte trace must cover at least two commit release windows")
    uncovered_ids = [attack_id for attack_id in committed_ids if attack_id not in released_ids]
    require(len(uncovered_ids) <= 1, "Acolyte trace missed a non-terminal commit release window")
    if uncovered_ids:
        final_state = acolyte[-1][1][2]
        require(
            uncovered_ids[0] == committed_ids[-1]
            and final_state.get("behaviorState") == "charge"
            and final_state.get("attackId") == uncovered_ids[0],
            "Acolyte uncovered commit was not an in-flight charge at the trace boundary",
        )

    for attack_id in covered_ids:
        appearances = []
        for snap in s:
            darts = [entry for entry in nodes_with(snap, "ownerSide", "enemy") if entry[2].get("attackId") == attack_id]
            require(len(darts) <= 1, f"Acolyte commit {attack_id} spawned more than one dart")
            if darts:
                appearances.append((snap, darts[0]))
        dart_node_ids = {dart[0] for _, dart in appearances}
        require(len(dart_node_ids) == 1, f"Acolyte commit {attack_id} did not spawn exactly one dart")
        snap, dart = appearances[0]
        acolyte_entry = nodes_with(snap, "kind", "shadow_acolyte")[0]
        player_entry = nodes_with(snap, "skill")[0]
        origin, target = node_position(acolyte_entry), node_position(player_entry)
        velocity = dart[1].get("physics", {})
        vx, vy = velocity.get("vx"), velocity.get("vy")
        dx, dy = target["x"] - origin["x"], target["y"] - origin["y"]
        require(all(isinstance(value, (int, float)) for value in (vx, vy, dx, dy)), "Acolyte dart aim evidence is missing")
        require(vx * dx + vy * dy > 0, "Acolyte dart was not aimed toward the player")
        require(abs(vx * dy - vy * dx) <= max(1, math.hypot(vx, vy) * math.hypot(dx, dy) * 0.03), "Acolyte dart aim diverged from the player")

    elite = []
    for snap in s:
        matches = nodes_with(snap, "kind", "dusk_deacon")
        if len(matches) == 1 and matches[0][2].get("attackId") == "elite-pulse":
            elite.append(matches[0])
    require(len(elite) == 2, "Elite pulse-immunity scenario needs before/after snapshots")
    require(node_position(elite[0]) == node_position(elite[1]), "Pulse pushed Dusk Deacon")
    require(elite[0][2].get("behaviorState") == elite[1][2].get("behaviorState"), "Pulse interrupted Dusk Deacon")


def assert_sigil_offers(s):
    require(len(s) >= 2, "sigil trace needs normal and final-pool offers")
    for index, snap in enumerate(s[-2:]):
        run = director(snap)
        offered = run.get("offeredSigils", [])
        owned = set(run.get("ownedSigils", []))
        require(len(offered) == 3 and len(set(offered)) == 3, "offer must contain three distinct sigils")
        require(set(offered) <= SIGILS and not (set(offered) & owned), "offer contains invalid or owned sigil")
        if index == 0:
            require(len({SIGIL_CATEGORIES[item] for item in offered}) >= 2, "normal offer contains fewer than two categories")
    final_run = director(s[-1])
    require(set(final_run.get("offeredSigils", [])) == SIGILS - set(final_run.get("ownedSigils", [])), "final pool must offer the exact remaining three")


def assert_sigil_effects(s):
    require(len(s) == 16, "sigil trace must contain all nine sigils plus combination scenarios")
    (
        base_s,
        piercing_s,
        ash_s,
        nail_s,
        light_s,
        rekindle_before_s,
        rekindle_after_s,
        wide_s,
        close_near_s,
        close_far_s,
        last_low_s,
        last_high_s,
        blood_before_s,
        blood_after_s,
        blood_reject_s,
        ash_nail_s,
    ) = s
    base = player(base_s)
    require((base.get("shotDamage"), base.get("shotsPerSecond"), base.get("movementSpeed"), base.get("maxHp")) == (20, 3, 260, 100), "base stats mismatch")

    piercing = player(piercing_s)
    piercing_bolts = projectiles(piercing_s, "player")
    require(piercing.get("shotDamage") == 16, "Piercing Ember damage must be 16")
    require(len(piercing_bolts) == 1 and piercing_bolts[0].get("damage") == 16 and piercing_bolts[0].get("pierceRemaining") == 1, "Piercing Ember bolt contract mismatch")

    ash = player(ash_s)
    ash_bolts = projectiles(ash_s, "player")
    require(close(ash.get("shotsPerSecond"), 2.4), "Ash Crown fire rate must be 2.4")
    require(len(ash_bolts) == 3 and all(b.get("damage") == 9 for b in ash_bolts), "Ash Crown must split into three 9-damage bolts")

    nail = player(nail_s)
    require(
        nail.get("shotDamage") == 40
        and close(nail.get("shotsPerSecond"), 1.8)
        and nail.get("projectileSpeed") == 570,
        "Sacred Nail derived stats mismatch",
    )
    require(len(projectiles(nail_s, "player")) == 1 and projectiles(nail_s, "player")[0].get("damage") == 40, "Sacred Nail shot mismatch")

    light = player(light_s)
    require((light.get("hp"), light.get("maxHp"), light.get("movementSpeed")) == (80, 80, 312), "Light Ember HP clamp/speed mismatch")
    require(light.get("hp") > 0, "Light Ember clamp incorrectly killed player")

    rekindle_before, rekindle_after = player(rekindle_before_s), player(rekindle_after_s)
    require(rekindle_before.get("shotDamage") == 17, "Rekindle shot penalty mismatch")
    require(rekindle_before.get("hp") == 50 and rekindle_after.get("hp") == 62, "Rekindle clear heal must be exactly 12")

    wide = player(wide_s)
    require(close(wide.get("pulseRadius"), 240), "Wide Radiance pulse radius must be 240")
    require(wide.get("skill", {}).get("cooldownRemaining", 0) > 11.8, "Wide Radiance cooldown must start at 12 seconds")

    require(enemies(close_near_s)[0].get("hp") == 30, "Close Flame near hit must deal 30")
    require(enemies(close_far_s)[0].get("hp") == 45, "Close Flame medium/long hit must deal 15")
    require(one(close_near_s, "reticleBand").get("reticleBand") == "close", "Close Flame near reticle band mismatch")
    require(combat_input(close_near_s).get("aim") == {"x": 800, "y": 360} and player(close_near_s).get("aimPoint") == {"x": 800, "y": 360}, "Close Flame near pointer/aim state mismatch")
    require(one(close_far_s, "reticleBand").get("reticleBand") == "far", "Close Flame far reticle band mismatch")
    require(combat_input(close_far_s).get("aim") == {"x": 1000, "y": 360} and player(close_far_s).get("aimPoint") == {"x": 1000, "y": 360}, "Close Flame far pointer/aim state mismatch")

    require(enemies(last_low_s)[0].get("hp") == 27, "Last Candle low-HP hit must deal 33")
    require(enemies(last_high_s)[0].get("hp") == 43, "Last Candle high-HP hit must deal 17")

    blood_before, blood_after, blood_reject = player(blood_before_s), player(blood_after_s), player(blood_reject_s)
    require(blood_before.get("hp") == 100 and blood_after.get("hp") == 92, "Blood Prayer must cost exactly 8 HP")
    require(close(blood_after.get("movementSpeed"), 325) and close(blood_after.get("shotsPerSecond"), 4.5), "Blood Prayer buff multipliers mismatch")
    require(blood_after.get("skill", {}).get("buffRemaining", 0) > 3.8, "Blood Prayer 4-second buff missing")
    require(blood_reject.get("hp") == 8 and blood_reject.get("skill", {}).get("lastRejected") not in (None, False, ""), "Blood Prayer low-HP rejection not atomic")
    require(blood_reject.get("skill", {}).get("cooldownRemaining", 0) <= 0 and blood_reject.get("skill", {}).get("buffRemaining", 0) <= 0, "rejected Blood Prayer started cooldown/buff")

    combo = player(ash_nail_s)
    combo_bolts = projectiles(ash_nail_s, "player")
    require(close(combo.get("shotsPerSecond"), 1.44), "Ash Crown + Sacred Nail sequential fire-rate order mismatch")
    require(len(combo_bolts) == 3 and all(b.get("damage") == 18 for b in combo_bolts), "Ash Crown split must occur before Sacred Nail multiplier")


def assert_stage_flow(s):
    require(len(s) == 12, "stage-flow trace must contain all stages, both Stage-4 branches, and wave transition")
    stage1, stage2, stage3, stage4_route, stage4_elite, stage5, stage6, pending, warning, warning_mid, wave2, stage7 = s
    order = director(stage1).get("layoutOrder", [])
    require(len(order) == 4 and len(set(order)) == 4, "ordinary layout order must contain four unique layouts")
    require(director(stage1).get("layoutId") == "open-vestibule", "Stage 1 must use fixed open vestibule")
    ordinary = [stage2, stage3, stage5, stage6]
    require([director(snap).get("stage") for snap in ordinary] == [2, 3, 5, 6], "ordinary stage sequence mismatch")
    require([director(snap).get("layoutId") for snap in ordinary] == order, "assigned layout order does not match Stage 2/3/5/6")
    expected_rosters = [
        (stage1, 2, 0),
        (stage2, 0, 3),
        (stage3, 2, 2),
        (stage5, 3, 2),
        (stage6, 2, 2),
        (wave2, 2, 3),
    ]
    for snap, fang_count, acolyte_count in expected_rosters:
        require(len(enemies(snap, "shadow_fang")) == fang_count, f"Stage {director(snap).get('stage')} Fang roster mismatch")
        require(len(enemies(snap, "shadow_acolyte")) == acolyte_count, f"Stage {director(snap).get('stage')} Acolyte roster mismatch")
        require(director(snap).get("enemyCount") == fang_count + acolyte_count, "director enemyCount does not mirror roster")
    require(director(stage6).get("wave") == 1 and director(wave2).get("wave") == 2, "Stage 6 wave index mismatch")
    require(director(stage4_route).get("stage") == 4 and director(stage4_route).get("runState") == "route" and director(stage4_route).get("enemyCount") == 0, "Stage 4 junction roster/state mismatch")
    require(len(enemies(stage4_elite, "dusk_deacon")) == 1 and director(stage4_elite).get("enemyCount") == 1, "Stage 4 Elite roster mismatch")
    require(director(stage7).get("stage") == 7 and len(enemies(stage7, "fallen_bishop")) == 1 and director(stage7).get("enemyCount") == 1, "Stage 7 Boss roster mismatch")
    require(director(pending).get("enemyCount") == 4 and director(pending).get("damagingObjectCount", 0) > 0, "wave-clear pending setup must retain dying Wave 1 roster and lingering damage")
    for snap in (warning, warning_mid):
        run = director(snap)
        require(run.get("enemyCount") == 0 and run.get("damagingObjectCount") == 0, "Wave 1 damage was not cleaned before warning")
        require(run.get("waveWarningActive") is True and run.get("wave") == 1, "Wave 2 warning state missing before spawn")
    require(director(wave2).get("waveWarningActive") is False, "warning remained active after Wave 2 spawn")
    player_entry = nodes_with(wave2, "skill")[0]
    for enemy_entry in nodes_with(wave2, "kind"):
        require(distance(player_entry, enemy_entry) >= 200, "Wave 2 enemy spawned inside near-body exclusion")


def assert_route_choice(s):
    require(len(s) == 9, "route trace must contain junction plus complete Recovery/Elite paths")
    junction_s, recovery_s, recovery_reenter_s, recovery_finish_s, elite_s, elite_clear_s, elite_reward_s, elite_reenter_s, elite_finish_s = s
    junction = director(junction_s)
    require(junction.get("stage") == 4 and junction.get("runState") == "route", "Stage 4 route junction missing")
    options_list = junction.get("routeOptions")
    require(isinstance(options_list, list) and {item.get("id") for item in options_list} == {"recovery", "elite"}, "both route options are not publicly observable")
    options = {item.get("id"): item for item in options_list}
    require(all(item.get("open") and item.get("interactable") and not item.get("locked") for item in options.values()), "both route options must start open and interactive")
    require(options["recovery"].get("heal") == 35 and options["recovery"].get("sigilReward") is False, "Recovery consequences incomplete")
    require(options["elite"].get("heal") == 10 and options["elite"].get("sigilReward") is True, "Elite consequences incomplete")
    require(all(item.get("label") and item.get("consequence") for item in options.values()), "route labels/consequences are incomplete")

    recovery = director(recovery_s)
    require(recovery.get("selectedRoute") == "recovery" and recovery.get("stage") == 5, "Recovery route did not lock and advance")
    require(player(recovery_s).get("hp") == 75, "Recovery route must restore exactly 35 HP")
    require(len(recovery.get("ownedSigils", [])) == 3, "Recovery route granted a forbidden sigil")
    recovery_options = {item.get("id"): item for item in recovery.get("routeOptions", [])}
    require(recovery_options.get("elite", {}).get("locked") is True and recovery_options.get("elite", {}).get("interactable") is False, "rejected Elite route remained interactive")
    require(director(recovery_reenter_s).get("selectedRoute") == "recovery" and director(recovery_reenter_s).get("stage") == 5, "re-entering rejected Elite route changed the run")
    require(len(director(recovery_finish_s).get("ownedSigils", [])) == 5, "Recovery route run must finish with five sigils")

    elite = director(elite_s)
    require(elite.get("selectedRoute") == "elite" and elite.get("stage") == 4, "Elite route did not lock in Stage 4")
    require(player(elite_s).get("hp") == 40 and len(elite.get("ownedSigils", [])) == 3, "Elite route healed or granted reward before victory")
    require(len(enemies(elite_s, "dusk_deacon")) == 1, "Elite route did not spawn exactly one Dusk Deacon")
    elite_options = {item.get("id"): item for item in elite.get("routeOptions", [])}
    require(elite_options.get("recovery", {}).get("locked") is True and elite_options.get("recovery", {}).get("interactable") is False, "rejected Recovery route remained interactive")
    require(player(elite_clear_s).get("hp") == 50, "Elite victory must restore exactly 10 HP")
    require(director(elite_clear_s).get("runState") == "reward" and len(director(elite_clear_s).get("offeredSigils", [])) == 3, "Elite victory did not offer a sigil reward")
    elite_reward = director(elite_reward_s)
    require(len(elite_reward.get("ownedSigils", [])) == 4 and elite_reward.get("stage") == 4, "Elite sigil selection state mismatch")
    require(elite_reward.get("exitOpen") is True and room(elite_reward_s).get("doorsClosed") is False, "Elite reward did not open the Stage 5 exit")
    elite_reenter = director(elite_reenter_s)
    require(elite_reenter.get("selectedRoute") == "elite" and elite_reenter.get("stage") == 4 and len(elite_reenter.get("ownedSigils", [])) == 4, "re-entering rejected Recovery route changed the run")
    rejected_door = room(elite_reenter_s).get("rejectedRouteDoor", {})
    require(rejected_door.get("routeId") == "recovery" and rejected_door.get("collisionActive") is True, "rejected Recovery door did not remain permanently locked")
    require(len(director(elite_finish_s).get("ownedSigils", [])) == 6, "Elite route run must finish with six sigils")


def assert_room_collision(s):
    require(len(s) == 18, "collision trace must contain eight blocked pairs plus open-door crossing")
    pairs = [s[index:index + 2] for index in range(0, 16, 2)]
    for before, _ in pairs:
        state = room(before)
        require(state.get("solidLayerReady") is True, "solid collision layer is not ready")

    def position_unchanged(a, b, field, value=None):
        before_nodes = nodes_with(a, field, value)
        after_nodes = nodes_with(b, field, value)
        require(len(before_nodes) == len(after_nodes) == 1, f"collision subject {field}={value} missing")
        pa, pb = node_position(before_nodes[0]), node_position(after_nodes[0])
        require(close(pa["x"], pb["x"], 1) and close(pa["y"], pb["y"], 1), f"{field}={value} crossed solid geometry")
        blocked = after_nodes[0][1].get("physics", {}).get("blocked", {})
        require(any(blocked.get(side) is True for side in ("left", "right", "up", "down")), f"{field}={value} did not report a solid collision")

    position_unchanged(*pairs[0], "skill")
    for before, after, label in ((pairs[1][0], pairs[1][1], "wall"), (pairs[5][0], pairs[5][1], "closed door")):
        fang_before = nodes_with(before, "kind", "shadow_fang")
        fang_after = nodes_with(after, "kind", "shadow_fang")
        require(len(fang_before) == len(fang_after) == 1, f"{label} Fang setup missing")
        require(node_position(fang_before[0]) == node_position(fang_after[0]), f"Pulse pushed Fang through {label}")
        require(player(after).get("skill", {}).get("cooldownRemaining", 0) > 0, f"Pulse did not execute against Fang at {label}")
    for before, after in (pairs[2], pairs[3], pairs[6], pairs[7]):
        projectile_before = nodes_with(before, "ownerSide")
        require(len(projectile_before) == 1, "projectile collision setup missing")
        attack_id = projectile_before[0][2].get("attackId")
        require(not nodes_with(after, "attackId", attack_id), "solid geometry failed to destroy projectile")
    position_unchanged(*pairs[4], "skill")

    opened, crossed = s[16], s[17]
    require(room(opened).get("doorsClosed") is False and director(opened).get("exitOpen") is True, "clear did not open exit")
    p0 = nodes_with(opened, "skill")[0]
    p1 = nodes_with(crossed, "skill")[0]
    require(node_position(p1)["y"] < node_position(p0)["y"] - 32, "opened door still blocked player passage")


def assert_boss_encounter(s):
    require(len(s) >= 8, "boss trace needs threshold/death cases plus attack-cycle samples")
    initial_s, transition_s, transition_hit_s, direct_death_s = s[:4]
    initial = enemies(initial_s, "fallen_bishop")[0]
    transition = enemies(transition_s, "fallen_bishop")[0]
    transition_hit = enemies(transition_hit_s, "fallen_bishop")[0]
    require((initial.get("hp"), initial.get("maxHp"), initial.get("phase")) == (1500, 1500, 1), "Boss initial state mismatch")
    require(transition.get("hp") == 740 and transition.get("behaviorState") == "phase-transition", "50% crossing did not enter transition")
    require(transition.get("damageEnabled") is False, "transition emitted damage")
    require(transition_hit.get("hp") == 720 and transition_hit.get("behaviorState") == "phase-transition", "transition blocked damage or was interrupted by hit")
    direct_run = director(direct_death_s)
    direct_boss = enemies(direct_death_s, "fallen_bishop")
    require(direct_run.get("runState") in {"victory-presentation", "victory"}, "50%-to-0 batch did not resolve directly to victory")
    if direct_boss:
        require(direct_boss[0].get("hp") == 0 and direct_boss[0].get("behaviorState") == "dead", "direct Boss death incorrectly entered transition")

    cycle_snaps = s[4:]
    boss_samples = [enemies(snap, "fallen_bishop")[0] for snap in cycle_snaps if enemies(snap, "fallen_bishop")]
    require(boss_samples and all(b.get("phase") == 2 for b in boss_samples), "phase-2 attack trace missing")
    require(all(b.get("consecutiveRanged", 99) <= 2 for b in boss_samples), "Boss exceeded two consecutive ranged attacks")
    require(all(b.get("damagePhaseActiveCount") in {0, 1} for b in boss_samples), "Boss damage phases overlapped")
    final_cycle = boss_samples[-1].get("phase2Cycle")
    require(isinstance(final_cycle, list) and len(final_cycle) == 3, "phase2Cycle must expose one complete three-attack group")
    require(sum(item == "ritual" for item in final_cycle) == 1, "each phase-2 group must contain exactly one ritual")

    sequence = boss_samples[-1].get("attackSequence")
    require(isinstance(sequence, list) and len(sequence) >= 3, "Boss completed attackSequence is missing")
    ranged_flags = [attack in {"spear", "ranged", "triple-shadow-spear"} for attack in sequence]
    require(not any(all(ranged_flags[i:i + 3]) for i in range(max(0, len(ranged_flags) - 2))), "Boss used ranged attacks three times consecutively")


def assert_boss_hazards(s):
    require(len(s) == 8, "hazard trace must contain warning, overlap, dedup, pulse, death, and post-death snapshots")
    warning, overlap_two, repeat_two, hit_third, repeat_third, pulsed, dead, post_dead = s
    warning_areas = areas(warning)
    require(len(warning_areas) == 3 and all(a.get("phase") == "warning" and a.get("damage") == 22 for a in warning_areas), "ritual must create three 22-damage warnings")
    require(len({a.get("attackId") for a in warning_areas}) == 3, "ritual areas need distinct attack ids")
    require(player(warning).get("hp") == 100, "warning phase dealt damage")

    overlap_areas = areas(overlap_two)
    require(len(overlap_areas) == 3 and all(a.get("phase") == "active" for a in overlap_areas), "all ritual areas must erupt together")
    require(sum(a.get("hitPlayer") is True for a in overlap_areas) == 2, "two overlapping ritual areas did not each register once")
    require(player(overlap_two).get("hp") == 56, "two overlapping areas must deal 44 total damage")
    require(player(repeat_two).get("hp") == 56, "ritual area repeated damage during one eruption")
    require(sum(a.get("hitPlayer") is True for a in areas(hit_third)) == 3 and player(hit_third).get("hp") == 34, "third ritual area did not deal its own single 22 damage")
    require(player(repeat_third).get("hp") == 34, "third ritual area repeated damage")

    require({a.get("attackId") for a in areas(pulsed)} == {a.get("attackId") for a in areas(repeat_third)}, "Pureflame Pulse removed ritual hazards")
    require(not projectiles(dead, "enemy") and not [a for a in areas(dead) if a.get("phase") == "active"], "Boss damage objects survived Boss HP 0")
    dead_boss = enemies(dead, "fallen_bishop")
    if dead_boss:
        require(dead_boss[0].get("damageEnabled") is False, "Boss damage remained enabled after death")
    require(player(post_dead).get("hp") == player(dead).get("hp"), "Boss projectile/hazard damaged player after Boss HP 0")


def assert_overlays(s):
    require(len(s) == 13, "overlay trace must cover pause/freeze/resume/confirm/cancel/choice/result/reload")
    running, paused_a, paused_b, resumed, confirm, confirm_pause, cancelled, resumed_again, choice, choice_pause, result, result_pause, reloaded = s

    def overlay(snap):
        return one(snap, "authority")

    def active_count(snap):
        visible = overlay(snap).get("visible", {})
        require(isinstance(visible, dict), "overlay visible map missing")
        return sum(value is True for value in visible.values())

    def motion_signature(snap):
        moving_nodes = []
        for entry in node_entries(snap):
            if "skill" in entry[2] or "kind" in entry[2] or "ownerSide" in entry[2]:
                moving_nodes.append((entry[0], node_position(entry), entry[2].get("behaviorState"), entry[2].get("attackId")))
        return moving_nodes

    require(overlay(running).get("authority") is None, "combat unexpectedly began modal")
    require(overlay(paused_a).get("authority") == overlay(paused_b).get("authority") == "pause", "pause authority changed")
    require(active_count(paused_a) == active_count(paused_b) == 1, "pause menus stacked")
    require(motion_signature(paused_a) == motion_signature(paused_b), "physics/Node state advanced while paused")
    require(player(paused_a).get("skill") == player(paused_b).get("skill"), "game timer advanced while paused")
    require(overlay(resumed).get("authority") is None and motion_signature(resumed) != motion_signature(paused_b), "Continue did not resume gameplay")

    require(overlay(confirm).get("authority") == overlay(confirm_pause).get("authority") == "restart-confirmation", "restart confirmation was replaced or stacked by PAUSE")
    require(active_count(confirm) == active_count(confirm_pause) == 1, "restart confirmation stacked menus")
    require(motion_signature(confirm) == motion_signature(confirm_pause) and player(confirm).get("skill") == player(confirm_pause).get("skill"), "restart confirmation did not freeze both clocks")
    require(overlay(cancelled).get("authority") == "pause", "Cancel did not return to unchanged pause menu")
    require(overlay(resumed_again).get("authority") is None, "Continue after cancel did not resume")

    require(one(choice, "optionIds").get("visible") is True and one(choice_pause, "optionIds").get("visible") is True, "PAUSE replaced sigil choice")
    require(overlay(choice).get("authority") is None and overlay(choice_pause).get("authority") is None, "PAUSE overlaid sigil choice")
    require(active_count(choice) == active_count(choice_pause) == 0, "sigil choice stacked an overlay menu")
    require(motion_signature(choice) == motion_signature(choice_pause) and player(choice).get("skill") == player(choice_pause).get("skill"), "sigil choice did not freeze both clocks")
    require(overlay(result).get("authority") == overlay(result_pause).get("authority") == "death", "PAUSE replaced/stacked terminal result")
    require(active_count(result) == active_count(result_pause) == 1, "terminal result stacked menus")
    require(motion_signature(result) == motion_signature(result_pause) and player(result).get("skill") == player(result_pause).get("skill"), "terminal result did not freeze both clocks")
    require(director(reloaded).get("bootId") != director(result).get("bootId"), "confirmed restart did not reload page")
    require(director(reloaded).get("stage") == 1 and director(reloaded).get("ownedSigils") == [], "confirmed restart did not reset run")


def assert_terminal_reset(s):
    require(len(s) == 3, "terminal trace needs lose, Boss mutual-win, and actual reload snapshots")
    lose_s, win_s, reset_s = s
    lose, win, reset = map(director, s)
    require(lose.get("layoutId") == "side-aisle-crypt", "lose setup layout was not pinned")
    require(lose.get("result", {}).get("outcome") == "lose", "lose result missing")
    require(lose.get("result", {}).get("remainingHp") == 0, "lose result HP must be zero")
    require(lose.get("result", {}).get("damageSource") == "Shadow Dart", "lose result damage source mismatch")
    require(win.get("result", {}).get("outcome") == "win", "win result missing")
    require(win.get("result", {}).get("remainingHp", 0) >= 1, "Boss mutual defeat must preserve at least 1 HP")
    require(not enemies(win_s, "fallen_bishop") or all(e.get("damageEnabled") is False for e in enemies(win_s, "fallen_bishop")), "Boss damage remained enabled after victory")
    require(reset.get("bootId") != win.get("bootId"), "Restart did not perform an actual page reload")
    require(reset.get("runId") != win.get("runId"), "Restart did not create a fresh run")
    require(reset.get("stage") == 1 and reset.get("ownedSigils") == [], "restart did not reset run state")
    require(reset.get("selectedRoute") is None and reset.get("damagingObjectCount") == 0, "restart leaked route/damage state")
    hero = player(reset_s)
    require((hero.get("hp"), hero.get("maxHp"), hero.get("shotDamage"), hero.get("shotsPerSecond")) == (100, 100, 20, 3), "restart did not restore base player stats")
    require(hero.get("skill", {}).get("ready") is True, "restart did not ready Pureflame Pulse")
    require(len(enemies(reset_s, "shadow_fang")) == 2 and not enemies(reset_s, "fallen_bishop"), "restart leaked old enemies or missed Stage 1 roster")
    require(not projectiles(reset_s) and not areas(reset_s), "restart leaked projectiles or hazards")
    require(not combat_input(reset_s).get("heldActions") and combat_input(reset_s).get("pointerFireSuppressed") is False, "restart leaked held/suppressed input")


def assert_hud_state(s):
    require(len(s) == 19, "HUD trace must contain intro, skill/reticle states, eight hit-window frames, TTL expiry, exit, and Boss snapshots")
    intro, intro_gone, cooldown, rejected, buff, close_near, close_far, damage_before = s[:8]
    damage_window = s[8:16]
    damage_expired, exit_open, boss = s[16:]

    def assert_hp_text(snap):
        hud = one(snap, "playerHpText")
        hero = player(snap)
        require(hud.get("playerHpText") == f"{hero.get('hp')} / {hero.get('maxHp')}", "HUD HP text mismatch")
        require(hud.get("sigilIds") == director(snap).get("ownedSigils"), "HUD sigils do not mirror run state")

    for snap in s:
        assert_hp_text(snap)
    hud_intro = one(intro, "roomIntroVisible")
    require(hud_intro.get("roomIntroVisible") is True and "1" in hud_intro.get("roomIntroText", "") and director(intro).get("roomName") in hud_intro.get("roomIntroText", ""), "room intro visibility/text mismatch")
    require(one(intro_gone, "roomIntroVisible").get("roomIntroVisible") is False, "room intro did not leave combat view")
    require(one(intro, "skillState").get("skillState") == "ready", "ready skill HUD state missing")
    require(one(cooldown, "skillState").get("skillState") == "cooldown", "cooldown HUD state missing")
    require(one(rejected, "skillState").get("skillState") == "rejected", "Blood Prayer rejection HUD state missing")
    require(one(buff, "skillState").get("skillState") == "buff", "Blood Prayer buff HUD state missing")
    require(one(close_near, "reticleBand").get("reticleBand") == "close", "close reticle band mismatch")
    require(combat_input(close_near).get("aim") == {"x": 800, "y": 360} and player(close_near).get("aimPoint") == {"x": 800, "y": 360}, "close pointer/aim state mismatch")
    require(one(close_far, "reticleBand").get("reticleBand") == "far", "far reticle band mismatch")
    require(combat_input(close_far).get("aim") == {"x": 1100, "y": 360} and player(close_far).get("aimPoint") == {"x": 1100, "y": 360}, "far pointer/aim state mismatch")
    require(enemies(damage_before, "shadow_fang")[0].get("hp") == 60, "damage-digit setup enemy HP mismatch")
    damage = next((snap for snap in damage_window if enemies(snap, "shadow_fang")[0].get("hp") == 40), None)
    require(damage is not None, "player bolt did not apply exact 20 damage during hit window")
    require(enemies(damage, "shadow_fang")[0].get("hp") == 40, "player bolt did not apply exact 20 damage")
    require(one(damage, "damageNumberCount").get("damageNumberCount", 0) > 0, "damage digits did not appear")
    require(one(damage_window[-1], "damageNumberCount").get("damageNumberCount", 0) > 0, "damage digit expired before evidence screenshot")
    require(one(damage_expired, "damageNumberCount").get("damageNumberCount") == 0, "damage digit runtime count did not clear after TTL")
    exit_hud = one(exit_open, "exitFeedbackVisible")
    require(exit_hud.get("exitFeedbackVisible") is True and exit_hud.get("exitFeedbackText"), "exit-open feedback missing")
    require(one(boss, "bossBarVisible").get("bossBarVisible") is True, "Boss bar hidden in Stage 7")
    require(one(intro, "bossBarVisible").get("bossBarVisible") is False, "Boss bar visible outside Stage 7")
    bars = [state.get("leftRate") for state in with_field(boss, "leftRate")]
    require(len(bars) == 2 and any(close(rate, 0.8) for rate in bars) and any(close(rate, 1) for rate in bars), "player/Boss status bars do not mirror exact HP ratios")


def assert_touch_input(s):
    require(len(s) == 23, "touch trace needs every semantic control, resumed pause state, and fire-suppression phases")
    expected = (
        "move_up",
        "move_down",
        "move_left",
        "move_right",
        "fire",
        "skill",
        "interact",
        "pause",
    )
    pairs = [s[index:index + 2] for index in range(0, 14, 2)]
    for action, (down, up) in zip(expected, pairs):
        down_state = combat_input(down)
        up_state = combat_input(up)
        require(down_state.get("inputSource") == "touch", f"{action} did not report touch input source")
        require(down_state.get("touchControlsVisible") is True, f"touch controls hidden during {action}")
        require(action_active(down_state.get("actionState", {}), action), f"touch {action} did not reach unified action state")
        require(not action_active(up_state.get("actionState", {}), action), f"touch {action} remained active after pointerup")

    signs = {
        "move_up": (0, -1),
        "move_down": (0, 1),
        "move_left": (-1, 0),
        "move_right": (1, 0),
    }
    for action, (down, up) in zip(expected[:4], pairs[:4]):
        velocity = player(down).get("velocity", {})
        sx, sy = signs[action]
        require((sx == 0 or velocity.get("x", 0) * sx > 0) and (sy == 0 or velocity.get("y", 0) * sy > 0), f"touch {action} did not move player")
        stopped = player(up).get("velocity", {})
        require(close(stopped.get("x"), 0, 1) and close(stopped.get("y"), 0, 1), f"touch {action} did not stop on release")

    fire_down, fire_up = pairs[4]
    require(player(fire_down).get("firing") is True and projectiles(fire_down, "player"), "touch fire did not shoot")
    require(player(fire_up).get("firing") is False, "touch fire remained active after release")
    skill_down, _ = pairs[5]
    require(player(skill_down).get("skill", {}).get("ready") is False and player(skill_down).get("skill", {}).get("cooldownRemaining", 0) > 0, "touch skill did not activate")
    interact_down, _ = pairs[6]
    require(director(interact_down).get("selectedRoute") == "recovery", "touch interact did not activate focused route")
    pause_down, pause_up, pause_resumed = s[14:17]
    require(combat_input(pause_down).get("inputSource") == "touch", "pause did not report touch input source")
    require(action_active(combat_input(pause_down).get("actionState", {}), "pause"), "touch pause did not reach unified action state")
    require(one(pause_down, "authority").get("authority") == "pause", "touch pause did not open pause overlay")
    require(one(pause_up, "authority").get("authority") == "pause", "pause pointerup incorrectly resumed game")
    require(not action_active(combat_input(pause_resumed).get("actionState", {}), "pause"), "pause remained active on first resumed frame")
    require("pause" not in combat_input(pause_resumed).get("heldActions", []), "pause held state leaked across resume")
    require(one(pause_resumed, "authority").get("authority") is None, "pause menu reopened after Continue")

    fire_held, suppressed, rejected, released, refired, refire_up = s[17:23]
    require(player(fire_held).get("firing") is True and projectiles(fire_held, "player"), "suppression setup did not hold touch fire")
    require(combat_input(suppressed).get("pointerFireSuppressed") is True and player(suppressed).get("firing") is False, "modal close did not suppress held touch fire")
    suppressed_ids = {p.get("attackId") for p in projectiles(suppressed, "player")}
    rejected_ids = {p.get("attackId") for p in projectiles(rejected, "player")}
    require(combat_input(rejected).get("pointerFireSuppressed") is True and player(rejected).get("firing") is False, "suppressed touch down leaked fire")
    require(rejected_ids <= suppressed_ids, "suppressed touch down spawned a projectile")
    require(combat_input(released).get("pointerFireSuppressed") is False and player(released).get("firing") is False, "touch release did not clear suppression")
    released_ids = {p.get("attackId") for p in projectiles(released, "player")}
    refired_ids = {p.get("attackId") for p in projectiles(refired, "player")}
    require(player(refired).get("firing") is True and bool(refired_ids - released_ids), "fresh touch down did not restore fire after release")
    require(player(refire_up).get("firing") is False, "restored touch fire remained active after release")


ASSERTIONS = {
    "run_start": assert_run_start,
    "input_edges": assert_input_edges,
    "projectiles": assert_projectiles,
    "pureflame_pulse": assert_pureflame_pulse,
    "skill_edges": assert_skill_edges,
    "damage_resolution": assert_damage_resolution,
    "enemy_behaviors": assert_enemy_behaviors,
    "sigil_offers": assert_sigil_offers,
    "sigil_effects": assert_sigil_effects,
    "stage_flow": assert_stage_flow,
    "route_choice": assert_route_choice,
    "room_collision": assert_room_collision,
    "boss_encounter": assert_boss_encounter,
    "boss_hazards": assert_boss_hazards,
    "overlays": assert_overlays,
    "terminal_reset": assert_terminal_reset,
    "hud_state": assert_hud_state,
    "touch_input": assert_touch_input,
}


def run_topic(topic):
    require(len(sys.argv) == 2, "usage: assert_<topic>.py SNAPSHOT_JSONL")
    try:
        ASSERTIONS[topic](load_trace(sys.argv[1]))
    except AssertionError as error:
        print(f"FAIL {topic}: {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"PASS {topic}")
