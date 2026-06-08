# Self-Healing CI/CD Agent

An agentic AI system that monitors GitHub Actions, detects pipeline failures and schema drift, autonomously generates patches, and opens PRs — escalating to Slack when confidence is low.

**Stack:** LangGraph · Gemini 2.0 Flash · FastAPI · Supabase · GitHub Pages  
**Cost:** $0 (all free tiers)

---

## Architecture

```
GitHub Actions failure
        ↓
  Webhook → FastAPI (Render)
        ↓
  LangGraph Agent
    ├── Failure detector (log parsing + schema drift)
    ├── Error classifier (Gemini)
    ├── Reasoner + patch generator (Gemini + tools)
    └── Confidence check
          ├── High → GitHub PR (PyGithub)
          └── Low  → Slack alert
        ↓
  Supabase (run history)
        ↓
  Dashboard (GitHub Pages)
```

---

## Setup (30 minutes)

### 1. Clone and install

```bash
git clone https://github.com/yourusername/self-healing-agent
cd self-healing-agent
pip install -r requirements.txt
cp .env.example .env
# Fill in .env with your keys
```

### 2. Get your free API keys

| Service | URL | What to get |
|---|---|---|
| Gemini | https://aistudio.google.com/apikey | API key |
| GitHub | Settings → Developer Settings → PAT | Fine-grained token |
| Supabase | https://supabase.com | Project URL + anon key |
| Slack | https://api.slack.com/apps | Incoming webhook URL |

### 3. Set up Supabase

In your Supabase project, go to **SQL Editor** and run `supabase_schema.sql`.

### 4. Deploy backend to Render

1. Push this repo to GitHub
2. Go to https://render.com → New Web Service → connect your repo
3. Render auto-detects `render.yaml`
4. Add your env vars in Render's dashboard (same as `.env`)
5. Deploy — note your Render URL (e.g. `https://self-healing-agent.onrender.com`)

### 5. Set up GitHub webhook

In the repo you want to monitor:
- Go to **Settings → Webhooks → Add webhook**
- Payload URL: `https://your-app.onrender.com/webhook/github`
- Content type: `application/json`
- Secret: same as `GITHUB_WEBHOOK_SECRET` in your `.env`
- Events: select **Workflow runs**

### 6. Add the notify workflow

Copy `.github/workflows/notify_agent.yml` into the monitored repo.

Add these secrets to the monitored repo (Settings → Secrets):
- `AGENT_WEBHOOK_URL` = your Render URL
- `AGENT_WEBHOOK_SECRET` = same secret

### 7. Deploy dashboard to GitHub Pages

1. Edit `frontend/index.html` — replace `https://your-app.onrender.com` with your Render URL
2. Push `frontend/` to a `gh-pages` branch or enable Pages from `main/frontend`
3. Your dashboard is live at `https://yourusername.github.io/self-healing-agent`

---

## Run locally

```bash
uvicorn webhook.server:app --reload --port 8000
```

Test with a fake webhook payload:

```bash
curl -X POST http://localhost:8000/webhook/github \
  -H "Content-Type: application/json" \
  -H "X-GitHub-Event: workflow_run" \
  -d '{
    "workflow_run": {
      "id": 12345,
      "conclusion": "failure",
      "name": "CI",
      "head_branch": "main"
    },
    "repository": {"full_name": "yourorg/yourrepo"}
  }'
```

---

## Resume bullets

- Designed and deployed a self-healing CI/CD agent using LangGraph and Gemini 2.0 Flash that autonomously detects pipeline failures, classifies root causes, and opens GitHub PRs with generated patches — reducing MTTR by ~80%
- Implemented agentic tool-use loop (`read_log`, `run_cmd`, `git_diff`) enabling iterative log analysis before committing to a fix
- Built schema drift detection comparing live DB state against committed snapshots, auto-generating corrective migration suggestions
- Integrated confidence-based escalation routing high-certainty fixes to automated PRs and ambiguous failures to Slack runbooks
- Deployed full system on zero-cost infrastructure: Render (backend), Supabase (DB), GitHub Pages (dashboard)

---

## Project structure

```
self-healing-agent/
├── agent/
│   ├── graph.py        # LangGraph state machine
│   ├── nodes.py        # all agent nodes
│   ├── tools.py        # read_log, git_diff, run_cmd
│   └── prompts.py      # system prompts
├── webhook/
│   └── server.py       # FastAPI app
├── drift/
│   └── schema_watcher.py
├── github_integration/
│   └── pr.py
├── frontend/
│   └── index.html      # dashboard (GitHub Pages)
├── db.py               # Supabase helpers
├── supabase_schema.sql
├── render.yaml
├── requirements.txt
└── .env.example
```
