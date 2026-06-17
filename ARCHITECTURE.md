# CodeSense — Architecture

## 1. System Overview

CodeSense is a GitHub App that automatically reviews pull requests using AI. When a PR is opened or updated, GitHub sends a webhook to the backend. Within 60 seconds, CodeSense fetches the diff, retrieves relevant context from the codebase, calls Claude claude-sonnet-4-6 to generate inline comments, and posts a GitHub PR review with exact line numbers, severity badges, and a verdict (Approve / Request Changes / Comment).

Beyond the first pass, CodeSense maintains a two-way conversation: developers can reply to individual inline comments, and CodeSense continues the thread using the original code context. Over time, it learns from the team's own review comments, injecting past examples into new LLM prompts so its style converges with the team's.

---

## 2. Why AST-Aware Chunking

Naive text splitting cuts files into fixed-size windows, breaking functions mid-body or grouping unrelated declarations together. This produces chunks with no semantic coherence: a chunk might contain half a function definition and the beginning of an unrelated class, making vector search results useless as context.

CodeSense uses **tree-sitter** to parse each file into an AST first. It then extracts top-level declarations (functions, classes, methods) as atomic units. A function body stays together regardless of length. If a declaration exceeds the token limit, it is split at a logical boundary (inner method, block statement) — never mid-expression.

The consequence for retrieval quality is significant. When reviewing a new function, a semantically similar chunk is most likely another function from the same codebase that shares logic, patterns, or data structures. AST-aware chunks contain exactly one such unit; text-split chunks may not.

---

## 3. Why MongoDB Atlas

A dedicated vector database (Pinecone, Weaviate) only stores vectors and metadata. CodeSense also needs document storage for: PR reviews (comments, summaries, status), conversation threads (multi-turn history), team style examples (embeddings + raw text), and feedback signals (reactions, deletions).

Running two separate databases would require synchronisation logic and double the operational overhead. MongoDB Atlas stores all of these as plain documents in the same cluster, and the **Vector Search** capability is built in via Atlas Search indexes — no separate service.

The critical architectural advantage is **filtered vector search in a single query**. A `$vectorSearch` aggregation stage can pre-filter by `repo_full_name` before computing cosine similarity, so a search for similar code never crosses repository boundaries. This is available natively; with a separate vector DB, you'd implement this with metadata filtering which varies by provider and often degrades performance.

---

## 4. RAG Pipeline Design

For each changed file in a PR, CodeSense runs a two-stage retrieval:

**Stage 1 — Semantic search.** The added lines are embedded with OpenAI `text-embedding-3-small` (1536 dimensions). A `$vectorSearch` aggregation finds the top-5 most similar code chunks from the same repo by cosine similarity. Results below a **0.75 threshold** are dropped.

The 0.75 threshold was chosen empirically: below it, matches tend to be superficially similar (same language constructs) but semantically unrelated (different domains). Above it, matches consistently represent the same pattern, abstraction, or data structure — useful context for a reviewer. The threshold is soft (the vector search's `numCandidates` pre-filters to 100, then cosine scores rank them), so false negatives at the boundary are low-cost.

**Stage 2 — Caller/callee search.** New function names extracted from the diff (via regex on added `+` lines) are looked up in `code_chunks` by text search. This finds existing call sites that use the new function — context the LLM uses to reason about compatibility and side effects.

Both result sets are merged, deduplicated by chunk name, and capped at 8 chunks before injection into the prompt.

**Team style retrieval.** A third `$vectorSearch` runs against the `team_style` collection, which holds embeddings of past human reviewer comments. The most semantically similar past comment (above the same 0.75 threshold) is injected as a few-shot example, shifting the LLM's tone and terminology toward the team's established patterns.

---

## 5. Prompt Engineering Decisions

The review prompt has two parts:

**System prompt** — sets the LLM's role as a senior engineer performing a code review. Instructs it to respond with a strict JSON schema: `{comments: [{line, severity, category, title, body}], file_summary, has_critical_issues}`. Structured output is enforced by instruction (not by API-level JSON mode) because the prompt includes reasoning instructions that benefit from prose thinking before the JSON.

**User prompt** — three optional sections injected as Markdown:
1. **Context section**: up to 8 code chunks from the codebase, labelled by file path, showing how this codebase handles similar patterns.
2. **Team style section**: 1–3 past reviewer comments with the code they annotated. The LLM sees real examples of what "a good review comment" looks like for this team before writing its own.
3. **The diff itself**: only the `+` lines, with their line numbers preserved so the LLM can output exact `line` values that GitHub's API requires.

When `team_style_chunks` is empty (new repo, no history yet), the section is omitted entirely — the prompt degrades gracefully without requiring a code path branch.

Severity is self-reported by the LLM and then used to sort comments (critical first) and determine the verdict: any critical → REQUEST_CHANGES, 4+ warnings → REQUEST_CHANGES, suggestions/info only → COMMENT, empty → APPROVE.

---

## 6. Webhook Architecture

GitHub sends webhooks synchronously and expects a 200 response within 10 seconds. A PR review (LLM call + two vector searches + GitHub API round-trips) takes 10–40 seconds. CodeSense handles this with **FastAPI background tasks**:

```
POST /webhooks/github
│
├── verify HMAC-SHA256 signature        ← synchronous, ~1ms
├── parse event type + action
├── add_background_task(handle_pull_request)
└── return {"status": "ok"}            ← 200 to GitHub in <100ms

  [background task]
  ├── fetch PR diff (GitHub API)
  ├── vector search × 2 (Atlas)
  ├── LLM call (Claude)
  └── post review (GitHub API)
```

Signature verification (`hmac.compare_digest` over the raw request body using the webhook secret) runs before any payload parsing, rejecting forged requests immediately.

Background tasks run in the same process as the FastAPI server. This is sufficient for current load (Railway single instance). At higher scale (1000+ PRs/day), background tasks would be replaced with a proper task queue (Celery + Redis or Railway Cron jobs) to survive server restarts mid-review and support horizontal scaling.

---

## 7. Scalability Considerations

The current design runs well for a single-tenant GitHub App handling dozens of repos. Key limits and their solutions at scale:

**Bottleneck: LLM latency per file.** Each file review is a sequential Claude API call. For a PR with 20 files, reviews run sequentially and can take 60–120 seconds total. Fix: `asyncio.gather` across files with a concurrency semaphore (cap at 5 parallel calls to avoid rate limits).

**Bottleneck: MongoDB Atlas M0 (512 MB RAM).** Free tier limits vector index size and concurrent connections. Fix: upgrade to M10+ when the corpus exceeds ~50K chunks or review latency degrades.

**Bottleneck: Railway single instance.** If the process restarts mid-review, the PR is never reviewed and the developer doesn't know. Fix: move background tasks to an external queue (Redis + Celery Worker on Railway) with at-least-once delivery. Store `status: "pending"` in MongoDB at task creation; a periodic job re-queues stalled pending reviews.

**Bottleneck: GitHub App rate limits.** Installation tokens are limited to 5000 requests/hour per installation. Large repos with frequent PRs can hit this. Fix: cache installation tokens (already done — `_token_expires_at` in `GitHubClient`). At very high scale, spread installations across multiple GitHub App registrations.

**Bottleneck: Embedding cost.** Each PR review generates 1 embedding per file (for team style retrieval) plus embeddings at index time. At 1000 PRs/day with 5 files average, that is 5000 embedding calls/day — well within OpenAI's free tier but worth monitoring. Fix at scale: batch embed using `client.embeddings.create` with multiple inputs per API call.
