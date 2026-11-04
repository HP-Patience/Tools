# Execution ledger — plan: docs/superpowers/plans/2026-10-17-react-fastapi-implementation.md

- Authorized: user approved inline execution, 2026-10-17.
- Ruling: use a development branch in the original clean checkout; no new worktree is necessary for this empty project. No external publish.
- Pre-flight A→B: cookie sessions and CSRF must cover every business API, including nested writes.
- Pre-flight B→C: all money integer fen; original Django model names are business contracts only, actual ORM is SQLAlchemy.
- Pre-flight C→D: revision updates must cancel pending old-expiry reminders atomically; network calls outside write transactions.
- Pre-flight D→E: CLI imports business modules, never depends on live HTTP API; shared SQLite path never lives in a release directory.
- Ruling: use focused domain files, avoiding per-entity layers with no behavior; keep interfaces typed and business operations isolated.
- Task A: in progress.

- Task A: complete — owner login, CSRF rotation, session expiry and logout; backend auth tests and browser login passed.
- Tasks B/C: implemented — catalog/customer APIs, typed inputs, exact money, calendar terms, transaction snapshots, duplicate UUID handling, revision checks, corrections and voids.
- Task D: implemented — durable reminder planner, batch claim and recovery, SMTP adapter, settings/log UI, CLI scheduler.
- Task E: deployment assets prepared — GitHub workflows pinned to verified official v6 commit SHAs, systemd, Nginx, SQLite backup/restore and release activation scripts. Live deployment awaits server configuration.
- Ruling: customer contacts stored as a validated JSON list on the customer, since no independent contact queries are needed beyond text search; preserves arbitrary contact types without an extra CRUD layer.
- Ruling: SQLAlchemy write transactions acquire BEGIN IMMEDIATE with bounded acquisition retry; SMTP calls are outside DB transactions. No PostgreSQL row locks.
- Ruling: fresh-context review via subagents is not used because the approved plan limits delegation. Perform local code review and regression checks; do not describe it as independent review.
- Browser finding: clearing the active authentication query during an initial 401 caused an endless loading state. Initial auth lookup now returns to login; session-expiry cleanup retains the auth query. Covered by the complete browser journey.
- Browser finding: wrapping selects within labels included option text in getByLabel matching. Form fields now use explicit separate label/id associations. Full keyboard-compatible dialogs trap focus and restore it on close.
- Local evidence so far: 33 backend tests passed, production build passed, complete Playwright workflow passed. Added explicit production HTTPS/TLS validation for final run.
- Remaining verification: final backend suite, Alembic check, frontend build/browser checks, static deployment syntax review and screenshots. No GitHub upload, SSH deployment or real SMTP delivery has occurred.

- Final review finding: restoring a previously cancelled expiry date did not reactivate its unsent reminder because the unique row already existed. Regression observed failing, planner now reactivates only cancelled unsent nodes; sent history remains untouched. Reminder suite passes.
- Final verification: complete browser journey passed after form label, mobile layout and auth fixes; desktop/mobile screenshots inspected. Backend final regression rerun recorded in delivery commit.
- Deployment static checks: Bash syntax, YAML parsing and Python parsing pass. Backup and isolated restore subprocess tests pass. Live Linux service activation, GitHub Actions execution and SMTP delivery remain unverified without target configuration.
- Ruling: keep the development branch in place; user will upload to GitHub. No remote push or merge performed.


## First-run administrator setup — 2026-10-17

- User requested first login to establish the administrator account.
- Added anonymous setup status and CSRF-protected, transactionally single-use setup endpoint; successful setup rotates the session and signs the owner in.
- Existing owner creation is rejected; password confirmation and minimum length are validated; concurrent creation tested.
- Frontend switches between first-run setup and normal login. CLI initialization remains optional.
- The known generated local preview owner was removed only after matching its saved generated credentials and creating a consistent backup; customer/sale counts stayed (4,4). Temporary credential file removed; user can now create their own account.
- Verification: 39 backend tests passed; frontend production build passed; Playwright covered first-run creation, logout, ordinary login and the full business flow; local preview inspected displaying setup form.


## README and repository delivery — 2026-10-17

- Canonical project copied to E:/项目管理/ai订阅客户管理, stable file sizes and source/data SHA256 hashes verified. Python venv upgraded in place and editable install rebound to the new location.
- Explicit setuptools app-only discovery fixes editable installation after data/alembic directories exist.
- Original C: directory remains a migration backup: recursive removal was rejected by automatic safety policy; safe rename also failed because the desktop app still holds the directory. Do not silently claim the old directory was removed.
- README rewritten concisely with a self-contained SVG hero and real desktop/mobile WebP screenshots; screenshot data is isolated and synthetic.
- Prior startup details preserved in docs/local-development.md; screenshot helper is reproducible and never opens the business database.


## Server deployment — 2026-10-17

- Connected to the requested Debian 13 host as work. Python 3.13.5 is available; passwordless sudo and user lingering are unavailable, so existing system services were left intact.
- Installed checksum-verified uv in the private application tools directory and deployed immutable releases under /home/work/apps/ai-subscriptions.
- Single FastAPI process serves the React production build and API on loopback 18080; users connect through an SSH tunnel. HTTP cookies remain local to the tunnel endpoint, external traffic is encrypted by SSH. No public uninitialized admin page was exposed.
- New production database created with migrations only; no local accounts, demo data or customer database uploaded.
- User cron starts/recovers the app, runs reminders every 15 minutes, and creates daily verified backups. Backup and reminder commands executed successfully on the host.
- Added a dedicated, restricted CI SSH key. Personal SSH credentials were never uploaded; existing authorized keys retained. CI key tested for upload/activation and rejection of unrelated shell commands.
- Configured repository deployment secrets, DEPLOY_ROOT and DEPLOY_ENABLED. CI run 38956975446 passed both verification and remote deployment.
- Regression: manual Windows archive contained a CRLF shell terminator. Shell LF validation and deployment normalization now prevent it; failed releases can be retried. 49 local backend tests passed.
- Remaining external configuration: public domain/HTTPS entrance and SMTP credentials. Reboot was not performed; cron startup entries are installed.


## Public HTTP access — 2026-10-17

- User explicitly requested direct HTTP by IP and port after opening cloud port 18080.
- Verified an administrator already exists before public exposure. Preserved the account and all business data.
- Configured APP_BIND_HOST=0.0.0.0 and APP_APP_URL=http://110.42.237.129:18080; kept HTTP-compatible cookie configuration. Runtime scripts use the configured bind address on future CI deployments.
- External probes confirmed public health, authentication status and HTML return 200; uninitialized administrator setup is closed.
- Real public-browser inspection found crypto.randomUUID unavailable on plain HTTP. Added a cryptographic getRandomValues UUID fallback; browser tests cover both UUID format/uniqueness and the complete transaction flow with randomUUID disabled.
- Local frontend build and both browser tests passed. Public access was requested without HTTPS; no certificate, proxy or privileged port changes were made.


## Form hierarchy — 2026-10-17

- Reorganized product, supplier, customer and transaction editors into task-based sections with concise instructions; secondary product metadata and quota fields use native disclosure controls.
- Shared field labels visibly distinguish required and optional inputs while preserving exact accessible names and associating help text with each control.
- Dialog titles and save actions remain fixed while form content scrolls; responsive fields use a single column on phones. Hidden disclosure controls are excluded from keyboard focus trapping.
- Product pricing includes a live reference margin; existing source links, warranty notes and other folded values remain part of the saved payload.
- Browser coverage checks required semantics, disclosure persistence, mobile overflow and save-button visibility alongside the existing purchase/renewal/profit workflow. Screenshots use the disposable test database only.


## In-app usage guidance — 2026-10-17

- Added a homepage checklist driven by current channels, priced active products, active customers and existing services, with a direct action for the next incomplete step. Shared query keys reuse current catalog/settings requests.
- Added permanent Chinese usage instructions at /guide and contextual expandable instructions on channel, product, customer, service, transaction and reminder pages. Copy explains imported inactive products, actual versus reference prices, coverage renewals and mail delivery to the administrator.
- Guide links can directly open add-customer, add-channel and purchase dialogs. Cancel/save consumes the route flag. A purchase with missing prerequisites offers links to create the missing records instead of presenting unusable selects.
- Catalog actions now include visible edit, enable/disable, archive/restore and delete labels. No business records are changed by viewing guidance.
- Browser workflow covers empty-state prerequisites, disabled-product readiness, direct guided actions, completion state, normal purchases/renewals and desktop/mobile layouts using disposable data.


## Favicon — 2026-10-17

- Added a branded SVG leaf icon for browser tabs, bookmarks and mobile home-screen metadata.
- Added a short site description and browser icon assertions to the end-to-end flow.
