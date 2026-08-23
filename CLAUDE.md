# app-ox2 — Project Context

This file captures the architecture decisions for `app-ox2`, the executable
that runs the orchestration pipeline against a checked‑out GitHub repository.
Update this file whenever a real decision changes.

---

## What this project is

A standalone CLI tool (`app-ox2`) that:
- Accepts a GitHub / git‑checked‑out repository path as input.
- Spins up a multi‑agent pipeline to turn plain‑text requirements into
  validated, committed code.
- Creates a `.ox2` folder (added to `.gitignore`) for intermediate and
  permanent instruction files. Agents can read/write/update/remove these
  files as requirements evolve.

---

## Agent Roles (Updated)

### Up‑front agents
- **Interaction Agent (new)** → clarifies user requirements, suggests best
  industry approaches, and passes confirmed requirements forward.
- **Requirement Enhancer Agent** → expands confirmed requirements into
  detailed specs (`.ox2/requirements.md`).
- **Business Analyst Agent** → validates requirements against business logic
  (`.ox2/business.md`).
- **Repo Analyst Agent** → analyzes repo structure and dependencies
  (`.ox2/repo.md`).
- **Dependency Agent** → installs/updates packages, logs actions
  (`.ox2/dependencies.log`).

### Inner correctness loop (Loop A)
- **Implementation Agent** → generates/edits code.
- **Verification Agent** → checks correctness (`.ox2/verification.log`).
  - FAIL → feedback → back to Implementation.
  - PASS → Compile Agent → build/compile (`.ox2/compile.log`).
    - FAIL → Implementation/Fix.
    - PASS → exit Loop A.
- Iteration capped at **3–5 attempts**.

### Outer quality gate (Loop B)
- **Security Agent** → runs audits (`.ox2/security.log`).
- **Lint Agent** → enforces style (`.ox2/lint.log`).
- **Test Agent** → runs unit/integration tests (`.ox2/test.log`).
- **Final Verification Agent** → ensures quality.
  - PASS → Doc Agent → updates docs (`.ox2/docs.md`) → Commit Agent.
  - FAIL → re‑enters Loop A with targeted feedback.
- Outer retries capped separately (e.g. 2).

### Finalization
- **Doc Agent** → updates README, inline comments, API docs.
- **Commit Agent** → commits only if all gates pass, logs metadata
  (`.ox2/commit.log`).

---

## Agent → API Mapping (with Fallbacks)

| Agent | Primary API | Fallback 1 | Fallback 2 | Final Fallback |
|-------|-------------|------------|------------|----------------|
| Interaction Agent | DeepSeek | Groq | OpenRouter | Gemini |
| Requirement Enhancer | DeepSeek | Groq | OpenRouter | Gemini |
| Business Analyst | DeepSeek | Meta LLaMA | Groq | Gemini |
| Repo Analyst | Gemini | DeepSeek | Meta LLaMA | Gemini (self-fallback) |
| Dependency Agent | Meta LLaMA | DeepSeek | Groq | Gemini |
| Implementation Agent (Code Editor) | DeepSeek | Groq | OpenRouter | Gemini |
| Verification Agent | Groq | DeepSeek | OpenRouter | Gemini |
| Compile Agent | Local execution | — | — | — |
| Security Agent | Amazon Bedrock (trial) | DeepSeek | Groq | Gemini |
| Lint Agent | Mistral AI | DeepSeek | Groq | Gemini |
| Test Agent | DeepSeek | Groq | Cerebras | Gemini |
| Doc Agent | Gemini | DeepSeek | Meta LLaMA | Gemini (self-fallback) |
| Commit Agent | OpenRouter | DeepSeek | Groq | Gemini |

---

## `.ox2` Folder Workflow

- Created automatically in repo root.
- Added to `.gitignore`.
- Contains intermediate/permanent files:
  - `requirements.md`
  - `business.md`
  - `repo.md`
  - `dependencies.log`
  - `compile.log`
  - `security.log`
  - `lint.log`
  - `test.log`
  - `docs.md`
  - `verification.log`
  - `commit.log`

Agents can refer back, enhance, add, or remove entries as requirements evolve.

---

## Provider / Capability Mapping

- **DeepSeek** → heavy coding, reasoning (Requirement Enhancer, Business Analyst, Implementation, Test).
- **Groq** → fast correctness checks (Verification, snippets).
- **Meta LLaMA (Hugging Face)** → dependency reasoning, open‑source fallback.
- **OpenRouter** → flexible commit agent, model switching.
- **Gemini** → final fallback for all agents (generalist, repo analysis, docs).

Agents declare **capabilities** (`fast-reasoning`, `deep-reasoning`, etc.),
never vendor SDK types. Provider mapping lives in `models/`.

---

## Tech stack

| Component | Standard / Selection |
|-----------|----------------------|
| Language runtime | Python 3.14+ |
| Package manager | uv |
| Agent foundation | Microsoft Agent Framework (>=1.15.0) |
| Primary provider SDK | google-genai (>=2.19.0) |
| Primary model alias | gemini-2.0-flash (or newer via env) |
| Dev environment | Mac / IntelliJ IDEA |

---

## Open questions

- Outer retry cap for Loop B (suggested 2, not confirmed).
- Exact schema for `ToolResult` structured findings.
- Whether downstream apps (e.g. `x2-forex-app`) have native iOS targets
  (determines `xcodebuild` adapter work).
- Test strategy for agents themselves (mocked vs live Gemini calls in CI).

---
