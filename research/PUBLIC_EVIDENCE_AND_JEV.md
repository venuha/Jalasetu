# Public evidence and Jev implementation notes

Access checks performed 24 October 2026 in America/Los_Angeles (25 October in India). These are observed test outcomes, not guarantees of continuing access.

| Source | Observed result | Implemented treatment |
| --- | --- | --- |
| [National Power Portal published reports](https://npp.gov.in/publishedReports) | HTTP 200; dynamically linked hydro and generation PDFs dated 22 October 2026 were downloadable and text extractable | Parse selected Srisailam/Nagarjuna Sagar hydro metrics and Telangana generation rows; retain dates, units, source PDF and page |
| [KRMB](https://krmb.gov.in/krmb/home) | Timed out in the direct network test | Try the dated table; report failure without substituting fixture values |
| [Open-Meteo](https://open-meteo.com/en/docs) | Forecast JSON returned successfully | Rain, probability and ET₀ preview at selected coordinates; not observed field rain |
| [IMD API reference](https://api.imd.gov.in/public/api_reference.html) | Tested subdivision endpoint returned 401, API key missing | Expose missing access; no guessed authentication implementation |
| [AP DES reservoir page](https://desweather.ap.gov.in/Realtime/ReservoirData.jsp) | TLS certificate verification failed | No TLS bypass; not an enabled collector |
| [Independent AP Reservoirs dashboard](https://ap-reservoirs.vercel.app/reservoirs/srisailam-r) | Latest section was retrievable | Optional, explicitly secondary storage/level records; attribution is not authenticated telemetry |
| [Tavily search](https://docs.tavily.com/documentation/api-reference/endpoint/search) | Documentation verified; credential required | POST search with bearer authentication and official-domain filters; returned excerpts remain discovery leads |

CEA effective hydro capacity is kept separate from gross storage. Telangana monitored generation is energy, not feeder availability or firm supply. Unknown command areas, local effective rain, engineering status and legal availability remain blockers for operational decisions.

## Jev: authority coordination only

Primary references: [TypeSafe introduction](https://docs.typesafe.ai/introduction), [API quickstart](https://docs.typesafe.ai/introduction/quickstart), [confidence definition](https://docs.typesafe.ai/confidence), and [Vercel routing example](https://vercel.com/academy/make-decisions-with-jev/run-the-template).

The implementation calls `POST https://api.typesafe.ai/v1/systemone` with bearer authentication, a configured model, a saved officer case/evidence state, and two Choice questions. Responsible desks: reservoir operations, irrigation planning, power coordination, engineering safety, joint review or clarification. Next steps: refresh evidence, run a scenario, request a power commitment, seek engineering review, seek officer review or obtain a field report.

The response must contain allowed labels, finite complete probability distributions summing approximately to one, a selected maximum-probability option and confidence consistent with the documented Choice formula. The 0.85 pilot threshold is not domain-calibrated. Model confidence is not a probability of engineering correctness. Low confidence, missing access and provider errors require manual officer triage. No release-approval option or write tool exists. An officer may override routing; that saves an assignment only. Reassessment clears the earlier assignment while retaining audit entries.

The separate five-role LLM panel uses read-only tools and structured cited assessments. Model integration follows [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling) and [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs); OpenAI uses Responses, supported compatible providers use chat completions. Exact model support is account-dependent. Paid-model and Tavily execution remain unverified until valid credentials are supplied. Mock tests verify mechanics, not prediction quality.
