# JalaSetu — Water Authority Console

An authority-operated React/Python decision-support prototype for Telangana irrigation departments, reservoir operators, power coordinators and ministry oversight. Farmers and village communities receive the outcomes; there is no farmer login or farmer-operated portal.

## Run locally

The compiled React bundle is included; Node is needed only to edit the frontend.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8092
```

Open http://127.0.0.1:8092. `Launch JalaSetu.command` can use this computer's existing Agentic System Python environment. Bind to loopback: this is a single-user prototype, without authenticated officials or production authorization.

## Authority workflow

1. **Authority overview:** selected-reservoir evidence, report dates, missing observations, coordination cases and scenario review counts. Unknown operating release availability stays unknown.
2. **Public evidence:** fetch dated CEA/National Power Portal hydro and generation PDFs, KRMB when reachable, an explicitly secondary reservoir dashboard and Open-Meteo forecasts. Failures stay visible; no synthetic readings replace unavailable public observations. Optional Tavily search discovers additional official-source leads.
3. **Authority case routing:** register an officer briefing. Jev recommends a responsible desk and next investigation step. Inspect option probabilities and model confidence; an officer confirms or overrides the assignment. Assignment does not approve a release or send a message.
4. **AI research panel:** an LLM researcher can select read-only search, forecast and scenario tools; three LLM specialists review water, command-area demand and energy in parallel; an LLM coordinator synthesizes cited findings. Independent checks preserve missing-data and operating-readiness limits. SQLite LangGraph checkpoints pause for human analysis review.
5. **Scenario planning:** separately labelled synthetic operating inputs demonstrate protected water pools, crop-stage priorities, canal limits, pump energy, daily power windows and delivery deadlines. Public report metrics are not silently substituted into incompatible planning fields.
6. **Review and delivery:** separate demo water and power reviews, freshness/hash validation, reservation checks and delivery observations.
7. **Field and feeder monitoring:** an officer evaluates supplemental field-water requirements, records demo rain/feeder events and checks excess-release observations. Outage and stale-reading alerts are in-app only.
8. **Beneficiary notices:** read-only village notice previews from simulations that passed both reviews. They never promise firm electricity from calculated pump-hours. No external messaging service is connected.

## Models and credentials

Open **Connections** and enter credentials there, not in chat. Entered keys stay in server process memory; they are not returned by status APIs, put in browser storage or saved in SQLite checkpoints. Restart clears entered keys. Server environment credentials remain until removed from the environment. `.env.example` documents variables; the server does not automatically load `.env` files.

| Capability | Connection | Without a key |
| --- | --- | --- |
| Public-source retrieval and arithmetic | No model key | Available, subject to network/source access |
| Five LLM research roles | OpenAI Responses or supported compatible provider; exact model ID with tools and structured output | Explicit `credentials_required`; no pretend model execution |
| Additional official-source discovery | Separate Tavily key | Direct public collectors still work; search reports not configured |
| Jev authority routing | Separate TypeSafe key, `jev-latest` or available account model | Case saved for manual officer triage; no invented choice |

Provider calls can incur charges. Jev receives the briefing and saved public evidence; the selected LLM provider receives the decision question, evidence excerpts and tool results; Tavily receives search queries. No live paid-model call has been verified without user-supplied credentials. Automated tests mock these calls and do not establish model accuracy.

Jev is one optional decision component alongside five LLM roles, not a sixth autonomous release authority. Its two Choice questions select a desk and a next review step. A pilot confidence threshold of 0.85 determines whether a routing recommendation is presented as sufficiently decisive; lower confidence requires human triage. The threshold is not domain-calibrated. Confidence summarizes the choice distribution, not measured correctness. The API validates labels, distributions and the documented confidence statistic. No actuation, approval or messaging tools are exposed. Jev does not replace water-balance calculations, engineering judgment or officer approval.

## Evidence boundaries

- CEA **effective hydro capacity at present level (MCM)** is not gross reservoir storage or authorized irrigation availability. **MU** is generated electrical energy; **MW** is power. State generation cannot establish a village feeder commitment.
- Retrieval time does not refresh an old reading. Observation dates, provenance, PDF page and measurement definitions are retained. Source schema changes fail visibly.
- KRMB can time out. IMD's tested endpoint requires authentication; it is shown unavailable when no access is established. Public websites are not necessarily documented public APIs. TLS checks are never bypassed.
- The independent reservoir dashboard is labelled secondary and requires corroboration. Search excerpts are discovery leads, not verified operating observations.
- Forecast rain is not measured effective field rain. Forecast-only advice is a review prompt; critical stress and flowering prevent generic deferral. Verified effective rain can reduce a supplemental application deficit to zero.
- There is no complete statewide village inventory, verified command connectivity, legal allocation engine, authenticated official identity, live dam engineering clearance, SCADA control or utility dispatch integration.

## Calculation sandbox

Eight named reservoir fixtures and sixteen fictional villages demonstrate calculations. All operating storage, reserve, route and village values remain synthetic, including fixtures resembling historical readings. A seed timestamp describes demo generation only. The default database is `data/jalasetu.sqlite3`; set `JALASETU_DB` for an independent environment.

Protected pool = max(operating floor, hydro hold) + drinking reserve + environmental reserve + other commitments. Components must be non-overlapping. Source volume = area ha × net depth mm × 10 / delivery efficiency. Lift energy follows ρgVH / efficiency. Allocation is crop-stage priority, proportional within a tier, bounded by source water, independent route capacity, power and delivery deadline. Hydro generation, basin-wide cascades, shared feeder concurrency and full-season crop demand are not modelled. Do not sum connected cascade storage as independently deliverable water.

Approved simulations reserve water against their snapshot and block dataset replacement until a production reconciliation process exists. Rain/power events invalidate pending proposal evidence; an outage creates a replan advisory, not a gate command. Feeder observations expire after ten minutes; rain credits expire after 24 hours. Village-wide rain coverage is an explicit demo assumption. Separate two-acre budgets never silently change a whole village's demand.

The Kaleshwaram schematic distinguishes sourced historical design, a hypothetical single-package lift calculator and unknown current safe operating capacity. See `research/KALESHWARAM_AND_FARMER_RULES.md`.

## Editing and validation

```bash
npm install
npm run build
.venv/bin/python -m pytest tests -q
```

Python 3.12+, Node 24 for the included bundle; `pnpm-lock.yaml` records frontend dependencies. SQLite retains cases, public snapshots, plans, reviews and deliveries; separate checkpoint databases retain scenario supervisor and research panel runs. They are excluded from GitHub and release archives along with credentials, virtual environments and dependencies.

The original deterministic scenario supervisor remains available as **Scenario workflow**. Its tool choices are rule-based. The separate **AI research panel** performs actual LLM tool selection when configured. Neither is represented as a trained hydrological predictor.

See `PROJECT.md` for architecture and `research/PUBLIC_EVIDENCE_AND_JEV.md` for source access and model references.
