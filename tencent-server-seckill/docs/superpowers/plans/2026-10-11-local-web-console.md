# Local Web Console Implementation Plan

> For agentic workers: use superpowers:executing-plans, inline execution explicitly authorized by the user. No additional approval gates; no delegated agents.

**Goal:** Ship a local Chinese Web interface that actually controls existing Python browser tasks.
**Architecture:** Python standard-library ThreadingHTTPServer serves static assets and same-origin JSON APIs. A locked TaskManager runs one unbuffered worker subprocess; worker reuses seckill core helpers and seckill_ui login helpers without interactive stdin prompts.
**Tech Stack:** Python 3.10+, existing Playwright, native HTML/CSS/JS, unittest, local browser verification.
**Spec:** docs/superpowers/specs/2026-10-11-local-web-console-design.md

## Global Constraints
- Loopback only, existing CLI unchanged; no new production dependency or Node build.
- No real Tencent requests or orders during verification; explicitly labelled --demo worker for browser tests.
- Validate Host, Origin, token, action, region, session and purchase confirmation.
- Strict login and CSRF checks; errors prevent purchase; state file existence is not proof of login.
- Stop cleans owned browser process tree, never other user browsers; already created orders are not cancelled.

## Review Focus
- Past specified session rolls to tomorrow; countdown uses backend calibrated clock.
- Missing/bad config preserves unrelated keys; state and secrets are never served.
- Concurrent starts, stale stop IDs and shutdown races never affect a newer task.
- Worker EOF without result never implies success; stop timeout escalates safely.
- Keyboard confirmation, network failures, HTML-shaped logs and narrow screens remain usable.

### Task 1: Task service and security
Files: seckill_web.py, tests/test_web.py.
- [x] Write failing tests for validation, file allowlist, token/origin guards, config merge, concurrency and stop lifecycle.
- [x] Run unittest to observe failure before implementing modules.
- [x] Implement TaskManager, bounded log sequence, typed worker events, status API and loopback HTTP handler.
- [x] Run tests; include failed launches, EOF, stale IDs and shutdown cleanup.

### Task 2: Noninteractive browser worker
Files: web_worker.py, tests/test_worker.py.
- [x] Write failing tests for session rollover, strict login, missing state/CSRF and connect never purchasing.
- [x] Implement login/connect/grab/test-order using existing core browser/token/time/purchase helpers and finally cleanup.
- [x] Listen for cooperative stop on stdin; publish explicit outcome and clock/login events.
- [x] Use harmless VIP request for prewarm, not existing warmup which can itself create an order before main purchase.
- [x] Implement deterministic --demo scenario with no imports/calls to browser or remote APIs.
- [x] Run tests using mocks, including cancellation cleanup.

### Task 3: Finished responsive UI
Files: web/index.html, web/styles.css, web/app.js.
- [x] Build intentional charcoal/acid-lime operations console, semantic forms, accessible modal and live logs.
- [x] Wire all operations to real APIs, confirm purchase, preserve local selections during polling and lock controls during tasks.
- [x] Recover after disconnect/reload using backend IDs, state and log cursor; clearly distinguish demo.
- [x] Validate full flows with local demo browser; inspect desktop/mobile screenshots and console errors.

### Task 4: Delivery and verification
Files: Web launcher bat, README.md, tests/browser_check.py.
- [x] Add venv/PATH Python detection and auto-open browser startup; document security, demo and order risk.
- [x] Run full unittest, compileall, JS syntax check and git diff --check.
- [x] Run local demo browser regression covering config, confirmation cancel, task result, logs, stopping and narrow screen.
- [x] Start normal idle service, open final product and report only verified results. Real login/payment remain user actions.

## Execution ledger
- User approved the spec and explicitly authorized implementation without further review gates.
- Ruling: use the clean existing checkout on codex/local-web-console so the final product is immediately available in the shared workspace; no merge, push, or external deployment.
- Ruling: keep seckill.py and seckill_ui.py unchanged; isolate all noninteractive adaptation in web_worker.py to preserve CLI behavior.
- Ruling: prewarm via get-vip-info, not warmup/do-goods, because the original prewarm can create real orders.
- Fixed and regression-tested: stopping must not hide an already confirmed purchase; driver cleanup still runs when browser cleanup is cancelled.
- Fixed and regression-tested: polling must not overwrite a newly selected session after a completed task; active session is restored on page reload.
- Fixed and regression-tested: 320px status cards must not force horizontal scroll; status cards allow shrinking/wrapping.
- Fixed and regression-tested: consume bounded POST body before rejection so Windows TCP close cannot discard the security response.
- Mock/fixture tests include a real, local-only unresponsive Python fixture to prove Windows process-tree forced stop. No Tencent requests or orders were used.
- Browser regression covers simulated login/connect/grab/test-order, confirmation cancel, checkbox gating, region persistence, reload, stop, log HTML escaping, follow/clear, disconnect/recovery and 1440/768/390/320px.
- Real-mode idle page was inspected and captured, with no task started. Original CLI --help remains functional.
- Final verification: 25/25 unittest tests pass; browser regression passes with zero unexpected console errors; JavaScript syntax check, Python compileall and git diff --check pass.
- Final product running at http://127.0.0.1:8765 in normal mode, idle, with no login/order task started by the agent. Temporary demo server stopped.
