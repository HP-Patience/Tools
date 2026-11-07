import json
import sys
from pathlib import Path


TESTS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TESTS_DIR))

from runtime_testlib import load_trace, node_entries, require, runtimes  # noqa: E402


EVIDENCE = Path(sys.argv[1]) if len(sys.argv) == 2 else None


def load_eval(name):
    payload = json.loads((EVIDENCE / name).read_text(encoding="utf-8"))
    require(not payload.get("error"), f"{name}: runtime eval failed: {payload.get('error')}")
    return payload.get("result", payload)


def runtime_with(snapshot, field):
    matches = [state for state in runtimes(snapshot) if field in state]
    require(matches, f"runtime field {field!r} is missing")
    return matches[0]


def player(snapshot):
    matches = [state for state in runtimes(snapshot) if "skill" in state and "hp" in state]
    require(matches, "PlayerController runtime state is missing")
    return matches[0]


def enemy(snapshot, kind):
    matches = [state for state in runtimes(snapshot) if state.get("kind") == kind]
    require(matches, f"enemy runtime state {kind!r} is missing")
    return matches[0]


def area(snapshot):
    matches = [
        state
        for _, node, state in node_entries(snapshot)
        if node.get("enabled") is not False
        and "warningDuration" in state
        and "visualTexture" in state
    ]
    require(len(matches) == 1, "expected exactly one observable telegraphed area")
    return matches[0]


def assert_action_trace(name, kind, expected):
    trace = load_trace(EVIDENCE / name)
    require(len(trace) == len(expected), f"{name}: expected {len(expected)} snapshots")
    observed = [
        player(snapshot).get("animationClip")
        if kind == "player"
        else enemy(snapshot, kind).get("animationClip")
        for snapshot in trace
    ]
    require(observed == expected, f"{name}: authored clip sequence {observed!r} != {expected!r}")

    for snapshot in trace:
        entries = [
            entry
            for entry in node_entries(snapshot)
            if (kind == "player" and "player" in entry[1].get("tags", []))
            or (kind != "player" and entry[2].get("kind") == kind)
        ]
        require(len(entries) == 1, f"{name}: expected one character node")
        physics = entries[0][1].get("physics", {})
        transform = entries[0][1].get("transform", {})
        require(
            all(isinstance(transform.get(axis), (int, float)) for axis in ("x", "y")),
            f"{name}: stable transform anchor is not observable",
        )
        require(isinstance(physics, dict), f"{name}: physics host is not observable")


def assert_melee(name, duration, warning_texture, impact_texture):
    warning, active = load_trace(EVIDENCE / name)
    before = area(warning)
    after = area(active)
    require(before.get("phase") == "warning", f"{name}: late warning window was not observable")
    require(after.get("phase") == "active", f"{name}: area did not enter active after warning")
    require(abs(before.get("warningDuration", -1) - duration) <= 0.001, f"{name}: warning override mismatch")
    require(after.get("warningDuration") == before.get("warningDuration"), f"{name}: resolved duration changed by phase")
    require(before.get("visualTexture") == warning_texture, f"{name}: warning texture mismatch")
    require(after.get("visualTexture") == impact_texture, f"{name}: impact texture mismatch")
    require(before.get("hitPlayer") is False, f"{name}: warning dealt damage")


def active_danger(snapshot):
    result = []
    for _, node, state in node_entries(snapshot):
        if node.get("enabled") is False:
            continue
        tags = set(node.get("tags", []))
        texture = state.get("visualTexture") or state.get("texture")
        if tags.intersection({"damaging", "hostile_projectile", "boss_hazard", "boss_projectile"}):
            result.append((tuple(sorted(tags)), state.get("phase"), texture))
    return result


def assert_cleanup():
    trace = load_trace(EVIDENCE / "stale-danger.jsonl")
    require(len(trace) == 6, "stale danger trace must contain three before/after pairs")
    fang_before, fang_after, room_before, room_after, boss_before, boss_after = trace
    require(active_danger(fang_before), "Fang cleanup setup did not contain owned danger")
    require(not active_danger(fang_after), "Fang death left owned warning/impact danger")
    require(active_danger(room_before), "room cleanup setup did not contain danger")
    require(not active_danger(room_after), "room clear left stale danger before reward")
    director = runtime_with(room_after, "runState")
    require(director.get("runState") == "reward", "room clear did not reach reward after cleanup")
    require(director.get("damagingObjectCount") == 0, "room clear retained damaging nodes")
    require(active_danger(boss_before), "Boss cleanup setup did not contain danger")
    require(not active_danger(boss_after), "Boss death left projectile/hazard danger")
    boss_director = runtime_with(boss_after, "runState")
    require(boss_director.get("runState") == "victory-presentation", "Boss death did not enter victory presentation")
    room = runtime_with(boss_after, "victoryLightingActive")
    require(room.get("victoryLightingActive") is True, "victory lighting was not activated after danger cleanup")


def assert_feedback_cap():
    first, second, expired = load_trace(EVIDENCE / "feedback-cap.jsonl")
    c1 = runtime_with(first, "damageNumberCount").get("damageNumberCount")
    c2 = runtime_with(second, "damageNumberCount").get("damageNumberCount")
    c3 = runtime_with(expired, "damageNumberCount").get("damageNumberCount")
    require(isinstance(c1, int) and 0 < c1 < 64, "damage digit feedback is not capped")
    require(c2 == c1, "damage digit count grew after reaching its cap")
    require(c3 == 0, "damage digits did not expire from runtime and DOM together")


def rect_inside(rect, bounds, tolerance=1.0):
    return (
        rect["left"] >= bounds["left"] - tolerance
        and rect["top"] >= bounds["top"] - tolerance
        and rect["right"] <= bounds["right"] + tolerance
        and rect["bottom"] <= bounds["bottom"] + tolerance
    )


def overlaps(a, b, tolerance=1.0):
    return not (
        a["right"] <= b["left"] + tolerance
        or b["right"] <= a["left"] + tolerance
        or a["bottom"] <= b["top"] + tolerance
        or b["bottom"] <= a["top"] + tolerance
    )


def assert_layout(name, require_three_cards=False, require_touch=False):
    result = load_eval(name)
    bounds = result["bounds"]
    elements = result["elements"]
    require(elements, f"{name}: no visible UI elements were measured")
    for item in elements:
        require(rect_inside(item["rect"], bounds), f"{name}: {item['label']} is outside viewport")
        require(item["scrollWidth"] <= item["clientWidth"] + 1, f"{name}: {item['label']} clips horizontally")
        require(item["scrollHeight"] <= item["clientHeight"] + 1, f"{name}: {item['label']} clips vertically")
    cards = [item for item in elements if item["role"] == "card"]
    if require_three_cards:
        require(len(cards) == 3, f"{name}: all three contract cards must be visible together")
        for index, card in enumerate(cards):
            for other in cards[index + 1 :]:
                require(not overlaps(card["rect"], other["rect"]), f"{name}: contract cards overlap")
    commands = [item for item in elements if item["role"] == "command"]
    for card in cards:
        for command in commands:
            require(not overlaps(card["rect"], command["rect"]), f"{name}: card overlaps a command")
    if require_touch:
        require(result.get("touchControlsVisible") is True, f"{name}: touch controls are not visible")
        require(result.get("authority") == "sigil-choice", f"{name}: resize lost modal authority")
        require(not any(result.get("actionState", {}).values()), f"{name}: resize resumed hidden combat input")


def assert_choice_actions():
    for name, expected in (
        ("text-reflow-choice.json", ["选择此契印"] * 3),
        ("viewport-resize-portrait.json", ["查看详情"] * 3),
    ):
        result = load_eval(name)
        actions = result.get("actions", [])
        require([item.get("text") for item in actions] == expected, f"{name}: action labels mismatch")
        for item in actions:
            rect = item.get("rect", {})
            require(rect.get("width", 0) > 0 and rect.get("height", 0) > 0, f"{name}: {item.get('label')} has a zero render box")
            require(item.get("scrollWidth", 0) <= item.get("clientWidth", 0) + 1, f"{name}: {item.get('label')} clips horizontally")
            require(item.get("scrollHeight", 0) <= item.get("clientHeight", 0) + 1, f"{name}: {item.get('label')} clips vertically")

    detail = load_eval("touch-detail-action.json")
    choice = detail.get("choice", {})
    actions = detail.get("actions", [])
    require(choice.get("visible") is True and choice.get("detailId") == "ash_crown" and choice.get("selectedId") is None, "touch detail selected before confirmation")
    require([item.get("text") for item in actions] == ["再次点击确认", "查看详情", "查看详情"], "touch detail action labels mismatch")
    require(actions and actions[0].get("ariaPressed") == "true", "touch detail aria-pressed state missing")
    for item in actions:
        rect = item.get("rect", {})
        require(rect.get("width", 0) > 0 and rect.get("height", 0) > 0, f"touch detail {item.get('label')} has a zero render box")
        require(item.get("scrollWidth", 0) <= item.get("clientWidth", 0) + 1, f"touch detail {item.get('label')} clips horizontally")
        require(item.get("scrollHeight", 0) <= item.get("clientHeight", 0) + 1, f"touch detail {item.get('label')} clips vertically")

    confirmed = load_eval("touch-confirm-action.json")
    choice = confirmed.get("choice", {})
    require(choice.get("visible") is False and choice.get("selectedId") == "ash_crown", "second touch did not confirm the selected sigil")
    require(confirmed.get("overlayPresent") is False and confirmed.get("cardCount") == 0, "confirmed touch choice overlay remained visible")


def assert_forbidden_and_sources():
    forbidden = load_eval("forbidden-semantics.json")
    require(forbidden.get("count") == 0, f"forbidden semantics found: {forbidden.get('matches')}")

    sources = load_eval("formal-source-scan.json")
    require(not sources.get("invalidVisuals"), f"non-formal runtime visuals: {sources.get('invalidVisuals')}")
    require(not sources.get("invalidDomAssets"), f"non-formal DOM assets: {sources.get('invalidDomAssets')}")
    require(sources.get("fontLoaded") is True, "vendored FusionPixel font did not load")
    require(not sources.get("remoteFontResources"), "font loaded from a remote/CDN URL")
    require(not sources.get("artifactResources"), "runtime loaded assets/artifacts content")
    require(not sources.get("placeholderResources"), "runtime loaded placeholder content")


def assert_formal_failures():
    result = load_eval("formal-asset-failure.json")
    visual = result["visual"]
    require(visual["rejected"] is True, "missing node image was not rejected")
    require(visual["magentaDelta"] == 0, "missing node image synthesized a magenta rectangle")
    animation = result["animation"]
    require(animation["rejected"] is True and animation["hidden"] is True, "missing atlas frame was not rejected and hidden")
    require(result["tilesetTexture"]["rejected"] is True, "missing tileset texture did not abort map construction")
    require(result["tileSemantic"]["rejected"] is True, "unknown tile semantic did not abort map construction")
    ui = result["ui"]
    require(ui["syncRejected"] is True, "missing UI manifest key did not throw")
    require(ui["asyncCleared"] is True and ui["asyncHidden"] is True, "failed UI image URL remained broken/visible")
    vfx = result["vfx"]
    require("__runtime_missing_vfx__" in vfx["missingTextureKeys"], "VFX owner did not record missing texture")
    require(vfx["hidden"] is True, "missing VFX retained its template visual")
    require(vfx["reported"] is True, "missing VFX did not reach RunDirector.assetFailures")


def main():
    require(EVIDENCE is not None and EVIDENCE.is_dir(), "usage: assert_visual_integration.py EVIDENCE_DIR")
    assert_action_trace("player-actions.jsonl", "player", ["idle", "run", "attack", "skill", "death"])
    assert_action_trace("fang-actions.jsonl", "shadow_fang", ["run", "attack", "death"])
    assert_action_trace("acolyte-actions.jsonl", "shadow_acolyte", ["move", "ranged-attack", "death"])
    assert_action_trace("deacon-actions.jsonl", "dusk_deacon", ["move", "melee-attack", "ranged-attack", "death"])
    assert_action_trace(
        "bishop-actions.jsonl",
        "fallen_bishop",
        ["move", "melee-attack", "ranged-attack", "summon", "phase-transition", "death"],
    )
    assert_melee("fang-melee.jsonl", 0.65, "fang_warning", "fang_impact")
    assert_melee("deacon-melee.jsonl", 0.85, "deacon_warning", "deacon_impact")
    assert_melee("bishop-melee.jsonl", 1.0, "bishop_warning", "bishop_impact")
    assert_cleanup()
    assert_feedback_cap()
    assert_forbidden_and_sources()
    assert_layout("text-reflow-choice.json", require_three_cards=True)
    assert_layout("text-reflow-route.json")
    assert_layout("text-reflow-result.json")
    assert_layout("viewport-resize-portrait.json", require_three_cards=True, require_touch=True)
    assert_choice_actions()
    assert_formal_failures()
    print("PASS visual_integration")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        print(f"FAIL visual_integration: {error}", file=sys.stderr)
        raise SystemExit(1)
