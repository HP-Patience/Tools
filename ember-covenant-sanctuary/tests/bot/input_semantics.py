META = {
    "name": "input_semantics",
    "purpose": "Exercise every desktop gameplay command through semantic action mappings.",
    "max_seconds": 12,
    "params": {"seed": "303"},
}


ACTIONS = (
    "move_up",
    "move_down",
    "move_left",
    "move_right",
    "fire",
    "skill",
    "interact",
)


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


def _action_active(action_state, action):
    value = action_state.get(action) if isinstance(action_state, dict) else None
    if isinstance(value, dict):
        return any(value.get(key) is True for key in ("held", "pressed", "active"))
    return value is True


def decide(snap, ctx):
    phase = ctx.scratch.setdefault("phase", "wait_combat")
    required = ACTIONS + ("pause",)
    missing = [name for name in required if name not in ctx.KEY]
    if missing:
        return ("fail", None, 0, f"missing semantic actions: {', '.join(missing)}")

    director = _runtime_with(snap, "runState")
    overlay = _runtime_with(snap, "authority")

    if phase == "wait_combat":
        if director and director.get("runState") == "combat":
            ctx.scratch["action_index"] = 0
            ctx.scratch["phase"] = "action_down"
            return ("down", ctx.KEY[ACTIONS[0]], 0.1, "press semantic move_up")
        if ctx.elapsed_s > 3.0:
            return ("fail", None, 0, "Stage 1 combat did not become controllable")
        return ("wait", None, 0.1, "wait for title overlay to clear")

    if phase == "action_down":
        action = ACTIONS[ctx.scratch["action_index"]]
        if action not in _held(snap):
            return ("fail", None, 0, f"{action} did not reach CombatInput")
        state = _runtime_with(snap, "actionState")
        if not state or state.get("inputSource") != "desktop":
            return ("fail", None, 0, f"{action} did not report desktop input source")
        if not _action_active(state.get("actionState", {}), action):
            return ("fail", None, 0, f"{action} did not reach unified actionState")
        ctx.scratch["phase"] = "action_up"
        return ("up", ctx.KEY[action], 0.06, f"release semantic {action}")

    if phase == "action_up":
        action = ACTIONS[ctx.scratch["action_index"]]
        if action in _held(snap):
            return ("fail", None, 0, f"{action} remained held after release")
        state = _runtime_with(snap, "actionState")
        if state and _action_active(state.get("actionState", {}), action):
            return ("fail", None, 0, f"{action} actionState remained active after release")
        index = ctx.scratch["action_index"] + 1
        if index < len(ACTIONS):
            ctx.scratch["action_index"] = index
            ctx.scratch["phase"] = "action_down"
            next_action = ACTIONS[index]
            return ("down", ctx.KEY[next_action], 0.1, f"press semantic {next_action}")
        ctx.scratch["phase"] = "pause"
        return ("tap", ctx.KEY["pause"], 0.15, "open pause via semantic action")

    if phase == "pause":
        if not overlay or overlay.get("authority") != "pause":
            return ("fail", None, 0, "pause action did not establish pause overlay authority")
        input_state = _runtime_with(snap, "actionState")
        if not input_state or input_state.get("inputSource") != "desktop":
            return ("fail", None, 0, "pause did not report desktop input source")
        ctx.scratch["phase"] = "resume"
        return ("tap", ctx.KEY["pause"], 0.15, "resume via semantic pause action")

    if overlay and overlay.get("authority") is not None:
        return ("fail", None, 0, "pause overlay remained authoritative after resume")
    return ("done", None, 0, "all desktop gameplay commands exercised semantically")
