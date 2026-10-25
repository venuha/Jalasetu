# JalaSetu

Water to field: a React and Python planning prototype connecting reservoir availability, village crop demand, pumping power, separate human reviews and delivery observations.

## Run locally

The production React bundle is included. Node is needed only when editing the frontend.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8092
```

Open http://127.0.0.1:8092. On this computer, `Launch JalaSetu.command` can also use the existing Agentic System Python environment. The service binds only to loopback. This is a single-user demo, not a shared authenticated government portal.

## Included

- Independent marine-blue React interface: ice-blue canvas, white navigation, modern sans-serif typography, water illustrations and a persistent agent workflow strip grounded in saved checkpoint state.
- Animated dam-to-tank landscape and interactive Kaleshwaram reverse-lift schematic, with keyboard-accessible nodes and reduced-motion support.
- Single-package Kaleshwaram lift-capacity calculator separating historical design, hypothetical power/flow envelopes, and unverified current availability.
- Durable LangGraph supervisor with conditional tool selection, bounded power alternatives, SQLite checkpoints and a real human interrupt that resumes across restarts.
- Two-acre farm water budget, verified-rain zero-demand rule, forecast-review gate, village rain events and feeder events connected to the planner.
- Farmer power-window updates, sudden-outage escalation and excess-release monitoring with event deduplication and in-app alerts.
- Eight example reservoir records and sixteen explicitly fictional villages. All operational values and routes are synthetic, not current readings.
- Total, protected, committed and proposable water shown separately for each source.
- Village search, crop stage, area, source route, lift head and delivery deadline.
- Water demand with soil/rainfall credits and delivery efficiency; drinking-water and environmental reserves retained.
- Lift energy, power capacity, per-day pump windows, canal capacity and travel-time constraints.
- Crop-stage priority and proportional allocation within each tier; insights about rescue irrigation and deferring expansion of new planting.
- Power-window comparison; stale-data, unavailable-weather and power-outage demonstrations.
- LangGraph calculation workflow; persistent SQLite proposal, review, reservation and delivery state.
- Separate water and power reviews, rejection, recalculation, data-hash checks, stale-evidence checks, and transactional prevention of double-booked water.
- Delivery observations and shortfall prompts, immutable-by-API history, downloadable evidence packets and validated demo dataset import/export.
- Live Open-Meteo weather adapter with timeout, retry and explicit fallback. Successful live access depends on network availability; forecast previews never silently change crop demand.
- Optional OpenAI-compatible model explanation with deterministic fallback. No model key is required to demonstrate the planning workflow.

## Demo walkthrough

1. Open Water overview: inspect protected reserves and village coverage. Note the synthetic-data banner.
2. Open Scenario planner and compare power windows. More electricity cannot unlock water protected for drinking or overcome a canal bottleneck.
3. Run a planning scenario. Inspect the evidence trail, source ledger, village allocations and daily pump windows.
4. Enter a demo water review and a separate demo power review. The result is a **simulated order**, not an external operation.
5. Record a partial source-equivalent delivery. Inspect the shortfall insight and audit history.
6. Create another scenario with `stale reservoir`: it pauses without approval controls. Try `power outage`: lifts stop but feasible gravity routes continue. `weather unavailable` produces an explicit manual-input fallback.
7. Refresh the page: saved proposals and reviews remain in SQLite.

## Editing and tests

```bash
# React frontend (pnpm or npm)
npm install
npm run build

# Python verification
.venv/bin/python -m pytest tests -q
```

`pnpm-lock.yaml` records the installed frontend dependency versions. Python requires 3.12 or newer; the implementation was tested using the existing 3.12 workspace runtime. Backend dependencies are bounded in requirements.txt. Node 24 was used for the included React build.

The database defaults to `data/jalasetu.sqlite3`; set `JALASETU_DB` for an independent demo database. Freshness is checked against the observation timestamp (48-hour limit). Sample timestamps are created once when a new database is initialized. If they expire, use a new demo database or upload a freshly generated demo dataset before approving; never relabel an old real observation as fresh.

## Optional model connection

Export `JALASETU_LLM_BASE_URL` (an OpenAI-compatible API base ending in `/v1` where required), `JALASETU_LLM_API_KEY`, and `JALASETU_LLM_MODEL` in the server environment. `.env.example` describes these variables; the server does not automatically load `.env` files. Suitable provider accounts include OpenAI-compatible providers offered by the course, subject to their current access and model support.

Only aggregate plan results and recommendation text are sent for explanation. Model responses are labelled review-required and do not alter calculations, approvals or orders. Missing credentials or an unavailable provider leaves deterministic insights operational. No live model call has been verified in this build.

## Important model boundaries

- The core planning workflow uses deterministic calculations with optional LLM explanation. The Agent command supervisor adds actual LangGraph SQLite checkpoints, conditional tool selection and a human analysis-review interrupt. It is not an autonomous hydrological forecasting model. Water and power approvals remain separate transactional API state transitions.
- There is no Telangana-wide village inventory or live official reservoir feed. All eight readings, capacities, operating floors, reserves, routes and sixteen village records are demo inputs. Srisailam's fixture resembles a previously researched secondary reading but is still synthetic here.
- Crop water depths are manually supplied supplemental irrigation inputs, not a full-season crop model or agronomic prescription. Drinking reserves are configured volumes, not population-based forecasts. Population is recorded but does not determine reserves in this version.
- Operating floor and hydro hold overlap; their maximum is retained. Drinking, environmental and other commitments are added as distinct, non-overlapping volumes. Their definitions need engineering review in a real deployment.
- Each reservoir is an independent pool with independent village routes. Shared canals, feeders, cascade transfers, upstream inflows, seepage, evaporation and legal allocations need explicit network and operating data before real use. Do not sum connected cascade volumes as independently deliverable water.
- Power windows are relative day schedules starting at 00:00 IST. They show energy and capacity feasibility under input assumptions, not a negotiated dispatch. The model assumes independent pumps/outlets; it does not verify shared-grid capacity.
- Hydro generation is not calculated. The configured hydro hold preserves a pool; releases used for downstream generation must be routed through a cascade model to avoid double counting.
- Approvals are demo role selections, not authenticated officials. There are no gate, SCADA, DISCOM, messaging or official-order integrations.
- Approved proposals reserve source water against this fixed snapshot, including after delivery observations, so the same water is not reused. Dataset replacement is blocked while approved reservations exist. Production requires measurement-based reconciliation and commitment lifecycle management.

See `PROJECT.md` for the course framework and roadmap, and `research/` for the preceding sources and feasibility work.

## Farmer event monitoring

Farmer & alerts supports a two-acre application budget, forecast preview, explicit village effective-rain observation, utility-window simulation, feeder-outage simulation and flow/volume anomaly detection. In-app alerts are generated when events are ingested; there is no unattended sensor ingestion daemon or external notification provider. The screen refreshes every 15 seconds while open. Event IDs deduplicate retries; changed payloads with reused IDs and out-of-order observations are rejected. Feeder readings expire after ten minutes, and expired commitments display unknown rather than available. Rain observations are replacement effective depths for the current application, not cumulative readings to be added; village-wide spatial coverage is a demo assumption and credits expire after 24 hours.

Rain and feeder events are included in proposal evidence guards. A changed event invalidates pending review; approved simulated orders remain historical records and an outage creates a replan advisory without operating hardware. The farm calculator does not automatically transfer a two-acre requirement to an entire village. Recording village rain is a separate, explicit action.

The farmer source volume is a supplemental application estimate based on the chosen depth, seepage allowance, field-water credit and delivery efficiency. Forecast-only rain can suggest deferring for review; critical stress and flowering prevent that generic forecast deferral. A zero deficit means no additional irrigation is proposed. Paddy advice is linked to FAO and ICAR and does not promise universal savings.
