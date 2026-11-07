META = {
    "name": "io_basic",
    "purpose": "Smoke-test Stage 1 semantic movement and primary fire wiring.",
    "max_seconds": 5,
    "params": {"seed": "101"},
}


def _runtime_values(snap):
    for node in snap.get("nodes", {}).values():
        runtime = node.get("runtime")
        if isinstance(runtime, dict):
            yield runtime


def _runtime_with(snap, field):
    return next((runtime for runtime in _runtime_values(snap) if field in runtime), None)


def _required_keys(ctx, names):
    return all(name in ctx.KEY for name in names)


def decide(snap, ctx):
    phase = ctx.scratch.setdefault("phase", "wait_combat")

    if not _required_keys(ctx, ("move_right", "fire")):
        return ("fail", None, 0, "semantic move_right/fire actions are missing")

    director = _runtime_with(snap, "runState")
    if phase == "wait_combat":
        if director and director.get("runState") == "combat":
            ctx.scratch["phase"] = "press_move"
            return ("down", ctx.KEY["move_right"], 0.12, "press semantic move_right")
        if ctx.elapsed_s > 2.8:
            return ("fail", None, 0, "Stage 1 combat did not begin after title")
        return ("wait", None, 0.1, "wait for title overlay to clear")

    input_state = _runtime_with(snap, "heldActions")
    player = _runtime_with(snap, "firing")

    if phase == "press_move":
        held = input_state.get("heldActions", []) if input_state else []
        if "move_right" not in held:
            return ("fail", None, 0, "move_right did not reach CombatInput")
        ctx.scratch["phase"] = "release_move"
        return ("up", ctx.KEY["move_right"], 0.05, "release semantic move_right")

    if phase == "release_move":
        held = input_state.get("heldActions", []) if input_state else []
        if "move_right" in held:
            return ("fail", None, 0, "move_right remained held after release")
        ctx.scratch["phase"] = "press_fire"
        return ("down", ctx.KEY["fire"], 0.16, "press primary fire")

    if phase == "press_fire":
        held = input_state.get("heldActions", []) if input_state else []
        if "fire" not in held or not player or player.get("firing") is not True:
            return ("fail", None, 0, "primary fire did not reach active gameplay")
        ctx.scratch["phase"] = "release_fire"
        return ("up", ctx.KEY["fire"], 0.08, "release primary fire")

    held = input_state.get("heldActions", []) if input_state else []
    if "fire" in held:
        return ("fail", None, 0, "fire remained held after release")
    return ("done", None, 0, "basic semantic movement and primary fire exercised")
