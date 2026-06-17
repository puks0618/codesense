# ⚡ CodeSense

**AI-powered pull request reviews for GitHub — inline comments, severity labels, and a verdict in under 60 seconds.**

CodeSense is a GitHub App that automatically reviews every pull request using Claude AI. It reads your code diff, retrieves semantically similar context from your codebase, and posts inline review comments directly on GitHub — exactly like a senior engineer would. Over time it learns your team's own review style and mirrors it.

---

## Demo

> Install the app → open a PR → get a review like this in under 60 seconds:

![CodeSense Dashboard](https://codesense-alpha.vercel.app)

**Live dashboard:** https://codesense-alpha.vercel.app

---

## Features

- **Instant PR reviews** — triggered the moment a PR is opened or updated, no manual action needed
- **Inline GitHub comments** — posted at exact line numbers with severity badges (🔴 Critical · 🟡 Warning · 🔵 Suggestion · ℹ️ Info)
- **Final verdict** — Approve, Request Changes, or Comment based on what was found
- **AST-aware context retrieval** — uses tree-sitter to chunk code by function/class boundaries, not arbitrary line windows
- **RAG pipeline** — semantic search over your codebase finds relevant existing functions before the LLM is called
- **Team style learning** — learns from your team's past review comments and injects them as few-shot examples
- **Conversation threads** — developers can reply to inline comments; CodeSense continues the thread with original context
- **Analytics dashboard** — see review history, issues by category, avg review time, and most flagged files per repo

---

## How It Works

```
Developer opens a PR
        │
        ▼
GitHub sends webhook → POST /webhooks/github
        │
        ├── Verify HMAC signature             (~1ms)
        ├── Queue background task
        └── Return 200 to GitHub              (<100ms)

        [Background Task]
        │
        ├── Fetch PR diff (GitHub API)
        ├── Parse changed files with tree-sitter (AST chunking)
        ├── Embed diff lines → vector search (MongoDB Atlas)
        │     ├── Stage 1: semantic similarity search (top-5 chunks, cosine ≥ 0.75)
        │     └── Stage 2: caller/callee lookup by function name
        ├── Retrieve team style examples (past reviewer comments)
        ├── Call Claude claude-sonnet-4-6 with context + diff
        │     → returns JSON: [{line, severity, category, title, body}]
        ├── Post inline review to GitHub API
        └── Store review + verdict in MongoDB
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python, FastAPI, Motor (async MongoDB) |
| AI | Anthropic Claude claude-sonnet-4-6 |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim) |
| Vector DB | MongoDB Atlas Vector Search |
| Code parsing | tree-sitter (AST-aware chunking) |
| GitHub integration | GitHub App (webhooks + REST API + PyJWT) |
| Frontend | React 18, Vite, React Router v6, Recharts |
| Auth | GitHub OAuth → HS256 JWT (24hr session) |
| Backend hosting | Railway (auto-deploy from master) |
| Frontend hosting | Vercel (auto-deploy from master) |

---

## Architecture Highlights

**Why AST-aware chunking?**
Naive text splitting cuts files at arbitrary line boundaries, breaking functions mid-body. CodeSense uses tree-sitter to extract top-level declarations (functions, classes, methods) as atomic units. A function body stays together regardless of length — producing semantically coherent chunks that make vector search actually useful.

**Why MongoDB Atlas for vectors?**
A dedicated vector DB (Pinecone, Weaviate) only stores vectors. CodeSense also needs document storage for PR reviews, conversation threads, and style examples. MongoDB Atlas combines both in one cluster — and supports filtered `$vectorSearch` that scopes results to a single repository in a single aggregation query.

**Why FastAPI background tasks?**
GitHub expects a webhook response within 10 seconds. A full review takes 10–40 seconds. FastAPI's `BackgroundTasks` lets the webhook handler return 200 immediately while the review runs asynchronously in the same process.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full design document.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- A GitHub account
- MongoDB Atlas account (free tier works)
- Anthropic API key
- OpenAI API key

### 1. Clone the repo

```bash
git clone https://github.com/puks0618/codesense.git
cd codesense
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials:

```env
GITHUB_APP_ID=your_app_id
GITHUB_CLIENT_ID=your_client_id
GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----
...your key...
-----END RSA PRIVATE KEY-----"
GITHUB_WEBHOOK_SECRET=your_webhook_secret
GITHUB_CLIENT_SECRET=your_client_secret
MONGODB_URI=mongodb+srv://...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
JWT_SECRET=your_random_secret_here
FRONTEND_URL=http://localhost:3000
```

Start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

### 3. Set up the frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```env
VITE_API_URL=http://localhost:8000
```

Start the frontend:

```bash
npm run dev
```

Visit `http://localhost:3000`

### 4. Register a GitHub App

1. Go to **github.com/settings/apps** → New GitHub App
2. Set the webhook URL to your backend (use [ngrok](https://ngrok.com) for local dev)
3. Set callback URL to `http://localhost:8000/auth/github/callback`
4. Request permissions: Pull requests (Read & Write), Contents (Read)
5. Subscribe to: Pull request events
6. Download the private key and paste it into `.env`

### 5. Create the MongoDB Vector Index

In MongoDB Atlas → your cluster → Search Indexes → Create Index:

```json
{
  "fields": [
    {
      "type": "vector",
      "path": "embedding",
      "numDimensions": 1536,
      "similarity": "cosine"
    },
    {
      "type": "filter",
      "path": "repo_full_name"
    }
  ]
}
```

Create one index named `code_vector_index` on the `code_chunks` collection, and another named `team_style_vector_index` on the `team_style` collection.

---

## Deployment

### Backend → Railway

1. Connect your GitHub repo to Railway
2. Set Root Directory to `backend`
3. Add all environment variables from `.env`
4. Railway auto-deploys on every push to `master`

### Frontend → Vercel

1. Import the GitHub repo into Vercel
2. Set Root Directory to `frontend`
3. Add environment variable: `VITE_API_URL=https://your-railway-url.railway.app`
4. Vercel auto-deploys on every push to `master`

After deploying the frontend, update `FRONTEND_URL` on Railway to your Vercel URL.

---

## Install CodeSense on Your Repo

**[→ Install the GitHub App](https://github.com/apps/codesense-reviewer/installations/new)**

1. Click Install and select your repository
2. Open a pull request
3. Within 60 seconds, CodeSense posts an inline review directly on your PR
4. Visit the dashboard to see metrics and full review history

---

## Project Structure

```
codesense/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, router registration
│   │   ├── config.py            # Pydantic settings (reads from .env)
│   │   ├── db/
│   │   │   └── client.py        # Motor async MongoDB client
│   │   ├── webhooks/
│   │   │   └── router.py        # GitHub webhook handler, PR review pipeline
│   │   ├── auth/
│   │   │   └── router.py        # GitHub OAuth, JWT session management
│   │   └── api/
│   │       └── router.py        # Dashboard REST API (/api/repos, /api/metrics)
│   ├── requirements.txt
│   └── tests/
│       └── test_webhooks.py     # 51 tests, 49 passing
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router, auth guard, token extraction
│   │   ├── api/client.js        # Axios instance with JWT interceptor
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx    # Repo list view
│   │   │   ├── RepoDetail.jsx   # Metrics, chart, PR history
│   │   │   └── PRReview.jsx     # Full review transcript, inline comments
│   │   └── components/
│   │       ├── Navbar.jsx
│   │       ├── RepoList.jsx
│   │       ├── ReviewCard.jsx
│   │       └── MetricsChart.jsx
│   └── package.json
└── ARCHITECTURE.md              # Full design document (7 sections)
```

---

## License

MIT
