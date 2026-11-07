import math


META = {
    "name": "player_combat",
    "purpose": "Verify directional input, independent aim, held fire, skill concurrency, and no defensive displacement state.",
    "max_seconds": 12,
    "params": {"seed": "202"},
}


DIRECTIONS = ("move_up", "move_down", "move_left", "move_right")
DIRECTION_SIGNS = {
    "move_up": (0, -1),
    "move_down": (0, 1),
    "move_left": (-1, 0),
    "move_right": (1, 0),
}

FORBIDDEN_DEFENSE_FIELDS = {
    "dodge",
    "roll",
    "dash",
    "teleport",
    "immunity",
    "invulnerability",
    "shield",
    "isinvincible",
    "invincible",
}


def _runtime_values(snap):
    for node in snap.get("nodes", {}).values():
        runtime = node.get("runtime")
        if isinstance(runtime, dict):
            yield runtime


def _runtime_with(snap, field):
    return next((runtime for runtime in _runtime_values(snap) if field in runtime), None)


def _held(snap):
    state = _runtime_with(snap, "heldActions")
    return set(state.get("heldActions", [])) if state else set()


def _fail_if_missing_keys(ctx):
    required = DIRECTIONS + ("fire", "skill")
    return [name for name in required if name not in ctx.KEY]


def _forbidden_runtime_fields(value):
    found = set()
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("_", "").replace("-", "").lower()
            suffixes = ("active", "state", "timer", "cooldown", "duration", "remaining", "ready", "enabled")
            if normalized in FORBIDDEN_DEFENSE_FIELDS or any(
                normalized in (f"is{field}", *(f"{field}{suffix}" for suffix in suffixes))
                for field in FORBIDDEN_DEFENSE_FIELDS
            ):
                found.add(str(key))
            found.update(_forbidden_runtime_fields(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_forbidden_runtime_fields(child))
    return found


def decide(snap, ctx):
    phase = ctx.scratch.setdefault("phase", "wait_combat")
    missing = _fail_if_missing_keys(ctx)
    if missing:
        return ("fail", None, 0, f"missing semantic actions: {', '.join(missing)}")

    director = _runtime_with(snap, "runState")
    player = _runtime_with(snap, "firing")
    input_state = _runtime_with(snap, "heldActions")

    forbidden = _forbidden_runtime_fields(list(_runtime_values(snap)))
    if forbidden:
        return ("fail", None, 0, f"forbidden defensive runtime fields: {', '.join(sorted(forbidden))}")

    if phase == "wait_combat":
        if director and director.get("runState") == "combat" and player and input_state:
            ctx.scratch["base_speed"] = player.get("movementSpeed")
            ctx.scratch["direction_start"] = player.get("position")
            ctx.scratch["direction_index"] = 0
            ctx.scratch["phase"] = "direction_down"
            return ("down", ctx.KEY[DIRECTIONS[0]], 0.12, "press move_up")
        if ctx.elapsed_s > 3.0:
            return ("fail", None, 0, "combat runtime fields did not become available")
        return ("wait", None, 0.1, "wait for controllable Stage 1 combat")

    if phase == "direction_down":
        index = ctx.scratch["direction_index"]
        action = DIRECTIONS[index]
        if action not in _held(snap):
            return ("fail", None, 0, f"{action} did not enter heldActions")
        velocity = player.get("velocity")
        position = player.get("position")
        start = ctx.scratch.get("direction_start")
        if not all(isinstance(value, dict) for value in (velocity, position, start)):
            return ("fail", None, 0, "player position/velocity runtime state is missing")
        sx, sy = DIRECTION_SIGNS[action]
        dx = position.get("x", 0) - start.get("x", 0)
        dy = position.get("y", 0) - start.get("y", 0)
        vx, vy = velocity.get("x", 0), velocity.get("y", 0)
        moved = (sx == 0 or dx * sx > 0 or vx * sx > 0) and (
            sy == 0 or dy * sy > 0 or vy * sy > 0
        )
        if not moved:
            return ("fail", None, 0, f"{action} produced no directional movement")
        ctx.scratch["phase"] = "direction_up"
        return ("up", ctx.KEY[action], 0.05, f"release {action}")

    if phase == "direction_up":
        index = ctx.scratch["direction_index"]
        action = DIRECTIONS[index]
        if action in _held(snap):
            return ("fail", None, 0, f"{action} remained held after release")
        index += 1
        if index < len(DIRECTIONS):
            ctx.scratch["direction_index"] = index
            ctx.scratch["direction_start"] = player.get("position")
            ctx.scratch["phase"] = "direction_down"
            next_action = DIRECTIONS[index]
            return ("down", ctx.KEY[next_action], 0.12, f"press {next_action}")
        ctx.scratch["phase"] = "aim"
        return ("mousemove", {"x": 1050, "y": 360}, 0.1, "aim independently to room right")

    if phase == "aim":
        aim = input_state.get("aim") if input_state else None
        if not isinstance(aim, dict):
            return ("fail", None, 0, "CombatInput did not expose aim state")
        ctx.scratch["aim"] = dict(aim)
        ctx.scratch["phase"] = "move_fire"
        keys = [ctx.KEY["move_up"], ctx.KEY["move_right"], ctx.KEY["fire"]]
        return ("down", keys, 0.42, "hold diagonal movement while firing")

    if phase == "move_fire":
        held = _held(snap)
        expected = {"move_up", "move_right", "fire"}
        if not expected.issubset(held):
            return ("fail", None, 0, "concurrent movement/fire actions were not retained")
        if player.get("firing") is not True:
            return ("fail", None, 0, "player did not report held firing")
        if player.get("movementSpeed") != ctx.scratch.get("base_speed"):
            return ("fail", None, 0, "firing changed applicable movement speed")
        velocity = player.get("velocity", {})
        speed = math.hypot(velocity.get("x", 0), velocity.get("y", 0))
        if not math.isclose(speed, ctx.scratch.get("base_speed"), abs_tol=2):
            return ("fail", None, 0, "moving while firing did not retain full speed")
        if input_state.get("aim") != ctx.scratch.get("aim"):
            return ("fail", None, 0, "movement changed independent aim")
        player_bolts = [
            runtime
            for runtime in _runtime_values(snap)
            if runtime.get("ownerSide") == "player"
        ]
        if not player_bolts:
            return ("fail", None, 0, "held fire produced no player projectile")
        if player.get("shotsPerSecond") != 3:
            return ("fail", None, 0, "base held-fire rate is not 3 shots per second")
        ctx.scratch["seen_shots"] = {bolt.get("attackId") for bolt in player_bolts}
        ctx.scratch["cadence_samples"] = 0
        ctx.scratch["phase"] = "cadence"
        return ("wait", None, 0.12, "sample held-fire cadence")

    if phase == "cadence":
        seen = ctx.scratch["seen_shots"]
        seen.update(
            runtime.get("attackId")
            for runtime in _runtime_values(snap)
            if runtime.get("ownerSide") == "player"
        )
        seen.discard(None)
        ctx.scratch["cadence_samples"] += 1
        if ctx.scratch["cadence_samples"] < 4:
            return ("wait", None, 0.12, "continue held-fire cadence sample")
        if not 2 <= len(seen) <= 4:
            return ("fail", None, 0, f"held fire produced {len(seen)} distinct shots in cadence window")
        ctx.scratch["pre_skill_position"] = dict(player.get("position", {}))
        ctx.scratch["pre_skill_hp"] = player.get("hp")
        ctx.scratch["phase"] = "skill"
        return ("tap", ctx.KEY["skill"], 0.12, "use skill while moving and firing")

    if phase == "skill":
        held = _held(snap)
        if not {"move_up", "move_right", "fire"}.issubset(held):
            return ("fail", None, 0, "skill interrupted held movement/fire inputs")
        if player.get("movementSpeed") != ctx.scratch.get("base_speed"):
            return ("fail", None, 0, "skill changed applicable movement speed")
        velocity = player.get("velocity", {})
        speed = math.hypot(velocity.get("x", 0), velocity.get("y", 0))
        if not math.isclose(speed, ctx.scratch.get("base_speed"), abs_tol=2):
            return ("fail", None, 0, "skill use interrupted full-speed movement")
        before = ctx.scratch.get("pre_skill_position", {})
        after = player.get("position", {})
        dx = after.get("x", 0) - before.get("x", 0)
        dy = after.get("y", 0) - before.get("y", 0)
        if dx <= 0 or dy >= 0 or math.hypot(dx, dy) > ctx.scratch.get("base_speed", 0) * 0.25:
            return ("fail", None, 0, "skill displaced, stopped, or reversed continuous movement")
        if player.get("hp") != ctx.scratch.get("pre_skill_hp"):
            return ("fail", None, 0, "base skill changed HP or implied protection cost")
        if player.get("animationClip") != "skill":
            return ("fail", None, 0, "skill did not select the authored skill clip")
        skill = player.get("skill")
        if not isinstance(skill, dict):
            return ("fail", None, 0, "player skill runtime state is missing")
        if skill.get("ready") is not False or not (skill.get("cooldownRemaining", 0) > 0):
            return ("fail", None, 0, "skill did not enter cooldown after use")
        ctx.scratch["phase"] = "release_all"
        keys = [ctx.KEY["move_up"], ctx.KEY["move_right"], ctx.KEY["fire"]]
        return ("up", keys, 0.1, "release movement and fire")

    if _held(snap).intersection({"move_up", "move_right", "fire"}):
        return ("fail", None, 0, "concurrent actions remained held after release")
    return ("done", None, 0, "direction, aim, held fire, and skill concurrency verified")
