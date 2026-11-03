# Where to test n8n and Dataiku (decided 2026-11-03)

Working note (not built into a PDF). envoituresimone was first meant as a Dataiku + n8n demo.
After discussion, neither tool fits it well: the app is one small table, a simple formula and
live per-user routing. So each tool gets a test project where it does real work, and
envoituresimone stays a plain web app (FastAPI + Leaflet, hourly price snapshot), with no
constraint from either tool.

## n8n -> the automatic meeting transcript bot

The bot (built 2026-11-03, deployed on Railway) waits for a new Teams transcript, processes it
with the Claude API, uses SharePoint and a GitHub token, and posts a summary to Slack.

Why it is the right n8n test:
- event-triggered, low volume, several services behind logins (Microsoft Graph, Anthropic,
  GitHub, Slack): n8n's sweet spot;
- n8n has nodes for SharePoint/OneDrive, Teams, Anthropic, GitHub and Slack, and handles
  OAuth refresh, polling, retries and run history;
- the code version already works: it is the known answer to compare against.

How:
1. Rebuild the same flow in n8n, keep the Railway version running.
2. Expect to call Graph's transcript endpoints with the generic HTTP Request node and a
   Microsoft OAuth2 credential (the Teams node may not cover them); admin consent is the same
   as for the code version.
3. Compare on the same meetings: summary quality, build time, failures, ease of change.
4. Watch: long transcripts (chunking, prompts) and tests are easier in code.

Possible follow-up: trigger yt-digest with n8n's RSS Feed Trigger on
`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`, n8n only starting the existing code
(webhook or GitHub Actions dispatch). Risk: YouTube often blocks transcript downloads from
datacenter IPs (Railway, n8n Cloud); check before moving it to the cloud.

Not for n8n:
- GENAU's missing-data warning to ntfy: do it in Prefect, which GENAU already uses (a check flow
  plus an automation on failed or late runs, webhook block to ntfy). A second scheduler would
  only add hosting and split the checks from the data.
- envoituresimone: the core app does not need it.

## Dataiku -> GENAU's mvp-software

mvp-software, with its experiments, already has hand-built source joins, recurring data
preparation, a model and a scheduled refresh: the right shape for Dataiku, and a known answer
to compare against.

How:
1. Port one slice end to end: two sources joined, preparation, the model, a scenario with
   checks, one output (dashboard or API service). Not the whole project.
2. Compare with the hand-built version: row counts, model scores, build time, what is easier or
   harder, how a colleague would take it over.
3. Schedule with Dataiku scenarios, not n8n: they are part of what is being tested.
4. Data: the Dataiku Cloud trial runs on Dataiku's servers and is deactivated after 14 days.
   Use anonymised or sample data unless GENAU and the client allow it. The downloadable Free
   Edition keeps data local but has no automation, so scheduling cannot be tested there.
5. The work lives in the mvp-software project, not here (this is a personal project).

## How Dataiku and n8n talk, for reference

- n8n -> Dataiku REST API (HTTP Request node, API key): run a scenario, check it, upload to a
  managed folder.
- n8n -> a Dataiku API service: `POST /public/api/v1/{service}/{endpoint}/predict`.
- Dataiku -> n8n: a scenario reporter or Python step posts to an n8n webhook.
- Shared storage: n8n drops files, a Dataiku dataset-change trigger picks them up.
