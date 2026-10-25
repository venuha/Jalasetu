# Render deployment: protected free sandbox

Deploy the existing GitHub repository with its root `render.yaml` Blueprint. The Blueprint uses a single Free Python web service, temporary local cloud storage and a generated management password. No paid disk is attached. Render may sleep the service when idle; requests can have a cold start. It disables automatic deploy-on-commit so future code updates are deployed deliberately.

## Runtime contract

- Python 3.12.12; install `requirements.txt`; the committed React production bundle needs no Node build in Render.
- Uvicorn listens on `0.0.0.0:$PORT`, one worker. `/api/health` is a public minimal health check; the app, API, documentation and assets require management access.
- `JALASETU_DB=/tmp/jalasetu/jalasetu.sqlite3` and `JALASETU_STORAGE_MODE=ephemeral`. The main database and both LangGraph checkpoint databases share a temporary directory. Saved cloud records may reset on restart or redeploy. Runtime data and Desktop records are excluded from GitHub; cloud starts fresh.
- `JALASETU_DEPLOYED=true` makes startup fail unless an absolute database path, management username, password of at least 20 characters and a single worker are configured.
- `JALASETU_ACCESS_USER=management`. Render generates `JALASETU_ACCESS_PASSWORD`; retrieve it yourself from the service's Environment settings. The app displays a management sign-in page. A successful login sets an eight-hour, HttpOnly, Secure, SameSite=Strict signed session cookie; the password is never stored in the browser. HTTPS is supplied by Render. Do not paste the password in chat or commit it.
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

The UI submits a background job and polls its status. The free sandbox can lose both job metadata and checkpoints when its temporary filesystem resets. One panel runs at a time, with a maximum of three running/queued jobs. SQLite graph checkpoints retain completed phases and the human-review interrupt. A process restart marks unfinished queue entries interrupted; the UI requests a new run rather than claiming they completed or silently repeating potentially billable calls. This queue is designed for one process and one replica. It is not a distributed job broker.

## After deployment

Verify Render reports Live, `/api/health` returns 200 and a request without credentials to `/api/dashboard` returns 401 and `/` redirects to the sign-in page. Sign in through the browser with the generated management credential and check the overview. Refresh public evidence and inspect failures/dates. Configure optional model keys to verify Jev and the LLM panel. Source availability can differ from local access; failed sources remain visible.

For durable records later, explicitly upgrade to a paid instance, attach a persistent disk, set JALASETU_DB to a path under its mount point and set JALASETU_STORAGE_MODE=persistent. Do not represent this free sandbox as durable storage. Export important demo packets before a restart. For production adoption, add government/organization SSO, per-user authorization, reconciled telemetry, independent backup/restore procedures, model evaluations and a durable external job/database architecture.

Sources: [Render Blueprint reference](https://render.com/docs/blueprint-spec), [persistent disks](https://render.com/docs/disks), [free service limits](https://render.com/docs/free).
