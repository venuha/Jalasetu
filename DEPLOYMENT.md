# Render deployment: protected management pilot

Deploy the existing GitHub repository with its root `render.yaml` Blueprint. Review the paid service/disk price in Render before creating it. The Blueprint uses a single Python web service, a 1 GB persistent disk and a generated management password. It disables automatic deploy-on-commit so future code updates are deployed deliberately.

## Runtime contract

- Python 3.12.12; install `requirements.txt`; the committed React production bundle needs no Node build in Render.
- Uvicorn listens on `0.0.0.0:$PORT`, one worker. `/api/health` is a public minimal health check; the app, API, documentation and assets require management access.
- `JALASETU_DB=/var/data/jalasetu.sqlite3`. The main database and both LangGraph checkpoint databases share the persistent disk directory. Runtime data and Desktop records are excluded from GitHub; cloud starts fresh.
- `JALASETU_DEPLOYED=true` makes startup fail unless an absolute database path, management username, password of at least 20 characters and a single worker are configured.
- `JALASETU_ACCESS_USER=management`. Render generates `JALASETU_ACCESS_PASSWORD`; retrieve it yourself from the service's Environment settings. The browser prompts for these credentials. HTTPS is supplied by Render. Do not paste the password in chat or commit it.
- This is one shared management sign-in for a pilot. It is not per-user identity, official role authorization, a signed legal release system or a public multi-tenant service. Share access only with intended reviewers.

## Optional model and discovery connections

Set secrets in the Render service's Environment settings, then deploy the change:

| Variable | Use |
| --- | --- |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | Exact accessible model supporting tools and structured output |
| `JALASETU_LLM_API_KEY`, `JALASETU_LLM_MODEL`, `JALASETU_LLM_BASE_URL` | Alternative supported provider configuration instead of the OpenAI pair |
| `TYPESAFE_API_KEY` | Jev authority case routing |
| `JALASETU_JEV_MODEL` | Optional exact Jev model; defaults to `jev-latest` |
| `TAVILY_API_KEY` | Optional official-source discovery |

Hosted Connections shows configuration status; it does not permit browser editing of shared provider credentials. Public-source retrieval and deterministic calculations require no paid model credential. External providers can charge for use by signed-in reviewers.

## Research jobs

The UI submits a background job and polls its status. One panel runs at a time, with a maximum of three running/queued jobs. SQLite graph checkpoints retain completed phases and the human-review interrupt. A process restart marks unfinished queue entries interrupted; the UI requests a new run rather than claiming they completed or silently repeating potentially billable calls. This queue is designed for one process and one replica. It is not a distributed job broker.

## After deployment

Verify Render reports Live, `/api/health` returns 200 and a request without credentials to `/api/dashboard` returns 401. Sign in through the browser with the generated management credential and check the overview. Refresh public evidence and inspect failures/dates. Configure optional model keys to verify Jev and the LLM panel. Source availability can differ from local access; failed sources remain visible.

Render's free service cannot attach this persistent disk. Do not switch to an ephemeral free instance while claiming that cases and approvals survive restarts. For production adoption, add government/organization SSO, per-user authorization, reconciled telemetry, independent backup/restore procedures, model evaluations and a durable external job/database architecture.

Sources: [Render Blueprint reference](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [free service limits](https://render.com/docs/free).
