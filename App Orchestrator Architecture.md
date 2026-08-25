# App Orchestrator Architecture

## 1. Purpose

`app-orchestrator` is a reusable, provider-agnostic AI software-development orchestration platform.

It accepts a natural-language software specification and/or an existing project `README.md` / requirements document, understands the target repository, recursively plans implementation, generates code incrementally, verifies the result, runs tests, updates documentation, and optionally prepares a commit.

The orchestrator is a separate top-level repository and must remain independent of application repositories it operates on.

```text
x2/

├── app-orchestrator/       # reusable orchestration platform
└── test-ox2/               # target application repository
```

The orchestrator is designed specifically for:

- incremental application generation;
- existing-project modification;
- changing requirements;
- bounded AI context;
- limited API availability;
- provider fallback;
- persistent project state;
- recursive work decomposition;
- minimal unnecessary LLM calls.

---

## 2. Core Principles

### 2.1 Provider agnostic

Agents never call an AI vendor SDK directly.

All models are accessed through a common provider abstraction and provider registry. Provider/model selection belongs in `mapping.yaml`.

### 2.2 Agent agnostic

Agents describe responsibilities, not vendors.

Provider chains are configuration-driven.

### 2.3 Repository is the implementation source of truth

AI output is a proposal.

The target repository is the authoritative implementation state.

Every generation cycle reads the current repository, applies a coherent change, verifies the result, and continues from the updated state.

### 2.4 Requirements are the product source of truth

The user's requirements and project README describe what the application should do.

`.ox2` stores the orchestrator's normalized understanding, execution plan, task state, dependencies, and implementation history.

The orchestrator must never assume that an old generated task is more authoritative than a changed user requirement.

```text
User Requirements / README
            |
            v
    Requirement Analysis
            |
            v
       .ox2 state
            |
            v
       Implementation
            |
            v
   Target Repository
```

### 2.5 Incremental generation

Large projects are decomposed into logical implementation work items.

Individual API requests remain bounded while the final repository can contain files much larger than one model response.

```text
Requirements
     |
     v
Adaptive Work Tree
     |
     +---- work item
     +---- work item
     +---- work item
              |
              v
       implementation
              |
              v
       repository state
```

### 2.6 API-call efficiency

The architecture must minimize unnecessary AI calls.

Planning should produce as much useful decomposition as possible in a single planning call.

Functions, classes, and files should not automatically cause separate AI requests.

The orchestrator should use deterministic operations for deterministic work:

- file operations;
- Git operations;
- state transitions;
- dependency ordering;
- hashing/diffing;
- build execution;
- test execution;
- path validation;
- artifact persistence.

AI calls should primarily be used where reasoning is required.

### 2.7 Small context, persistent state

Do not repeatedly send the whole repository to the model.

Persist important state in `.ox2`, workspace artifacts, implementation plans, task metadata, and verification results.

Each model call receives only the relevant bounded context.

### 2.8 Recursive decomposition

The Workflow Agent decides how much a requirement needs to be broken down.

There is no mandatory fixed hierarchy such as:

```text
Requirement → Functionality → Task → Subtask → Function
```

Instead, work is represented as a recursive work tree.

```text
Work Item
   |
   +-- small enough → executable
   |
   +-- too large → decompose
                         |
                         +-- Work Item
                         +-- Work Item
                         +-- Work Item
```

The same decomposition mechanism is reused recursively.

### 2.9 Maximum decomposition depth

Recursive decomposition must be bounded.

The normal maximum is **2–3 decomposition levels**.

The planner should stop as soon as a work item is independently implementable and verifiable.

If the work is still too large after the configured maximum depth, the orchestrator must not create an increasingly deep hierarchy.

Instead, it should ask the user to split the functionality into smaller requirements.

```text
Requirement
    |
    v
Level 1
    |
    v
Level 2
    |
    v
Level 3
    |
    +---- implementable → execute
    |
    +---- still too large → ask user to split
```

The depth limit is configuration/policy, not duplicated across multiple classes.

### 2.10 Fail gracefully

Provider failures must be classified and handled according to retryability.

Retryable failures may fall back to the next configured provider/model.

Non-retryable failures should fail fast.

---

# 3. High-Level Architecture

```text
                         USER
                           |
                           v
                  +-------------------+
                  |   CLI / Entry     |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | Orchestrator /    |
                  | Pipeline          |
                  +---------+---------+
                            |
          +-----------------+------------------+
          |                 |                  |
          v                 v                  v
 +----------------+ +----------------+ +----------------+
 | Pipeline State | |   Workspace    | | Configuration  |
 +----------------+ +----------------+ +----------------+
                            |
                            v
                  +-------------------+
                  |   .ox2 State      |
                  | Requirements      |
                  | Workflow          |
                  | Pending           |
                  | Implemented       |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | Workflow /        |
                  | Planning Agent    |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | Recursive Work    |
                  | Tree              |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | Implementation    |
                  | Agent             |
                  +---------+---------+
                            |
                            v
                  +-------------------+
                  | Provider Registry |
                  +---------+---------+
                            |
             +--------------+--------------+
             |              |              |
             v              v              v
          Gemini         DeepSeek        Groq ...
             |
             v
      Target Repository
             |
             v
        Verification
             |
             v
           Tests
             |
             v
      Documentation
             |
             v
          Commit
```

---

# 4. Major Components

## 4.1 CLI / Entry Point

Responsible for:

- accepting requirements;
- identifying the target repository;
- loading configuration;
- initializing workspace/state;
- starting the pipeline;
- displaying progress;
- reporting the final result.

It must not contain provider-specific logic.

---

## 4.2 Orchestrator / Pipeline

Coordinates:

- requirement analysis;
- reconciliation;
- planning;
- work-tree execution;
- provider registry;
- workspace;
- pipeline state;
- artifacts;
- verification;
- failures;
- final status.

Ordering is deterministic even though model responses are probabilistic.

The orchestrator controls execution state.

The AI decides what should be done; the orchestrator decides when and how that work is executed.

---

## 4.3 Workflow / Planning Agent

The Workflow Agent is responsible for understanding the requirement and deciding the appropriate implementation decomposition.

It does **not** need separate agents/classes for:

- functionality analysis;
- task analysis;
- subtask analysis;
- function analysis.

Instead, it recursively creates a work tree.

```text
Requirement
    |
    v
Workflow Agent
    |
    v
Work Item
    |
    +-- executable
    |
    +-- composite
           |
           +-- Work Item
           +-- Work Item
           +-- Work Item
```

The planner determines:

- scope;
- dependencies;
- acceptance criteria;
- implementation boundaries;
- whether a work item is executable;
- whether further decomposition is necessary.

### Planner stopping rule

A work item is executable when it is:

1. sufficiently small;
2. independently understandable;
3. independently implementable;
4. independently verifiable;
5. bounded enough for the configured model/context;
6. not dependent on unresolved work that must be completed first.

If those conditions are not satisfied, it is recursively decomposed.

---

# 5. Work Tree Architecture

The work tree replaces a rigid class hierarchy.

A work item can represent a:

- requirement;
- functionality;
- task;
- subtask;
- implementation unit.

These are conceptual descriptions rather than mandatory object types.

A work item contains information such as:

```text
id
parent_id
description
requirement_ids
acceptance_criteria
dependencies
children
status
revision
executable
affected_files
verification
```

A work item with children is a composite work item.

A work item without children and marked executable is an implementation work item.

### Example

```text
REQ-001
Authentication
|
+-- WORK-001
|   Backend authentication
|   |
|   +-- WORK-001-01
|       OAuth provider integration
|
+-- WORK-002
    Frontend authentication
    |
    +-- WORK-002-01
        Login UI
```

Only executable leaf work items need implementation calls.

---

# 6. `.ox2` Project State

`.ox2` is the persistent orchestration state of the target project.

Recommended structure:

```text
.ox2/

├── requirements.md
├── workflow.md
├── pipeline_state.json
│
├── pending/
│   ├── TASK-001/
│   │   ├── task.md
│   │   └── subtasks.md
│   │
│   └── TASK-002/
│       ├── task.md
│       └── subtasks.md
│
├── implemented/
│   ├── TASK-003/
│   │   ├── task.md
│   │   └── subtasks.md
│   │
│   └── TASK-004/
│       ├── task.md
│       └── subtasks.md
│
└── generation/
```

The exact internal representation may evolve, but the conceptual distinction between `pending` and `implemented` should remain.

### Pending

Work that needs to be implemented or reimplemented.

### Implemented

Work whose implementation and required verification have successfully completed.

---

# 7. Requirements and Reconciliation

The orchestrator must support existing projects and changing requirements.

Initial project:

```text
README.md
    |
    v
Requirement Analyzer
    |
    v
.ox2/requirements.md
    |
    v
Workflow / Work Tree
    |
    v
Implementation
```

When the user changes the README:

```text
New README
    +
Existing .ox2 state
    |
    v
Requirement Reconciliation
    |
    v
Change Impact Analysis
```

The reconciler identifies:

- new requirements;
- modified requirements;
- removed requirements;
- unchanged requirements;
- affected functionality;
- affected work items.

---

# 8. Incremental Requirement Changes

The orchestrator must not regenerate the entire project because one requirement changed.

Example:

```text
implemented/

TASK-001
TASK-002
TASK-003
TASK-004
TASK-005
```

A new requirement affects only:

```text
TASK-003
TASK-004
```

The reconciler changes their state:

```text
implemented/
    TASK-003
    TASK-004

        |
        v

pending/
    TASK-003
    TASK-004
```

Unaffected work remains implemented.

### Important

An implemented task returning to pending is not necessarily a new task.

It should retain:

- task identity;
- requirement relationship;
- history/revision;
- reason for invalidation.

For example:

```text
TASK-003
revision: 2
status: pending
reason: requirement-change
```

This allows the orchestrator to understand that it is revising existing implementation rather than creating unrelated work.

---

# 9. Requirement Traceability

Every executable work item should be traceable back to its requirements.

Conceptually:

```text
REQ-007
   |
   +-- WORK-021
   |      |
   |      +-- TASK-021-01
   |
   +-- WORK-022
          |
          +-- TASK-022-01
```

This allows a requirement change to find affected implementation without rediscovering the entire repository.

Work items should therefore maintain relationships to:

- requirement IDs;
- parent work items;
- dependent work items;
- affected files;
- implementation revisions.

---

# 10. Dependency and Impact Propagation

Work items may depend on other work items.

Example:

```text
TASK-010 Database
      |
      v
TASK-011 Repository
      |
      v
TASK-012 Service
      |
      v
TASK-013 API
```

When `TASK-010` changes, the orchestrator identifies potentially affected downstream work.

It must not automatically invalidate everything.

Instead:

```text
Changed:
TASK-010

Potentially affected:
TASK-011
TASK-012
TASK-013

Impact analysis:

TASK-011 → affected
TASK-012 → affected
TASK-013 → unaffected
```

Only confirmed affected work returns to `pending`.

This minimizes unnecessary implementation calls.

---

# 11. Requirement Versioning

Requirements should have stable identities and revisions.

Conceptually:

```text
REQ-007
revision 1
    |
    v
revision 2
    |
    v
revision 3
```

Tasks should record which requirement revision caused their implementation.

This allows the orchestrator to determine:

- why a task exists;
- why a task was invalidated;
- what requirement changed;
- which implementation revision corresponds to the requirement.

Full Git-style requirement history is not initially required.

---

# 12. Obsolete Work

When a requirement is removed, its existing implementation should not simply disappear from orchestration history.

The work item should be marked obsolete.

```text
REQ-015
    |
    v
TASK-044
    |
    v
obsolete
```

The implementation may remain in the repository until the user explicitly approves its removal.

This prevents accidental destructive changes.

---

# 13. Agent Architecture

The architecture should avoid creating a class/agent for every conceptual level.

Initial logical responsibilities:

```text
interaction
requirement
workflow
reconciliation
repo_analysis
dependency
implementation
verification
security
lint
test
documentation
commit
```

These are responsibilities, not necessarily one class per name.

### Interaction

Normalizes the user's initial request.

### Requirement

Understands and normalizes requirements.

### Workflow

Recursively decomposes requirements into an executable work tree.

### Reconciliation

Compares current requirements against `.ox2` state and determines what changed.

### Repository analysis

Inspects language, framework, architecture, important files, conventions, reusable code, and conflicts.

### Dependency

Checks existing dependencies first and identifies compatibility risks.

### Implementation

Turns executable work items into working code.

### Verification

Determines whether implementation satisfies acceptance criteria.

### Security

Reviews secrets, unsafe input/file operations, dependency risk, authentication/authorization issues, and obvious security weaknesses.

### Lint

Runs or evaluates language-specific lint/static-analysis checks.

### Test

Runs existing tests and generates tests where appropriate.

Test generation should not automatically become a separate API call for every work item.

### Documentation

Updates README/project documentation so it reflects the actual implementation.

### Commit

Reviews final state and prepares a meaningful commit message.

Git mutation only occurs when explicitly enabled.

---

# 14. Recursion Instead of Class Explosion

The architecture explicitly prefers:

```text
data
+
recursion
+
workflow composition
```

over:

```text
RequirementAnalyzer
FunctionalityAnalyzer
TaskAnalyzer
SubtaskAnalyzer
FunctionAnalyzer
...
```

A single recursive mechanism should handle decomposition.

Conceptually:

```text
process(work_item)

    if implemented:
        return

    if executable:
        implement()
        verify()
        return

    decompose()

    for child:
        process(child)
```

The actual implementation may use workflows/functions rather than a literal recursive method, but the architectural principle remains.

### Exception

Separate abstractions are appropriate when there is genuinely different behavior or an external boundary, such as:

- provider adapter;
- repository/workspace;
- verifier;
- Git adapter;
- shell execution;
- configuration.

A new class should not be created merely because a new noun appears in a requirement.

---

# 15. API Call Strategy

Limited API availability is a first-class architectural constraint.

The desired pattern is:

```text
1 planning/reconciliation call
        |
        v
complete work tree
        |
        v
implementation calls for executable work
        |
        v
verification/correction only when required
```

Not:

```text
requirement call
    ↓
workflow call
    ↓
functionality call
    ↓
task call
    ↓
subtask call
    ↓
function call
```

### Planning

The Workflow Agent should preferably produce the complete useful decomposition in one call.

### Implementation

One implementation call should handle as much logically related implementation as safely possible.

For example:

```text
One executable work item

    |
    +-- model
    +-- repository
    +-- service
    +-- API endpoint
    +-- validation

            ↓

       one implementation call
```

Functions do not automatically become separate API requests.

### Deterministic operations

Do not consume AI calls for:

- moving pending/implemented tasks;
- calculating hashes;
- comparing files;
- reading directories;
- validating paths;
- executing builds;
- running tests;
- recording state;
- ordering known dependencies.

---

# 16. Adaptive Decomposition Example

Simple requirement:

```text
Add a health endpoint.
```

The planner may decide:

```text
REQ
 |
 +-- executable work item
```

No unnecessary hierarchy is created.

Medium requirement:

```text
Add user authentication.
```

The planner may create:

```text
REQ
 |
 +-- Backend authentication
 |      |
 |      +-- OAuth/session implementation
 |
 +-- Frontend authentication
        |
        +-- Login integration
```

Large requirement:

```text
Build an entire payment platform.
```

The planner may create:

```text
REQ
 |
 +-- Payment processing
 |      |
 |      +-- Payment creation
 |      +-- Payment confirmation
 |
 +-- Refunds
 |      |
 |      +-- Refund processing
 |
 +-- Webhooks
        |
        +-- Webhook handling
```

If an individual work item is still too large at the maximum planning depth:

```text
Planner
   |
   v
Still too large
   |
   v
STOP
   |
   v
Ask user to split functionality
```

The system must not recursively decompose indefinitely.

---

# 17. Incremental Code Generation

Incremental generation is a core capability designed for large repositories and constrained/free API tiers.

## 17.1 Input

The implementation generator receives:

- relevant requirements;
- executable work item;
- repository analysis;
- dependency analysis;
- current repository state;
- relevant existing files;
- implementation configuration;
- relevant verification failures.

A large README is allowed as an input artifact, but it should not be blindly sent in full with the entire repository on every implementation request.

---

## 17.2 Planning

The Workflow Agent creates the work tree before implementation.

The Implementation Agent should not rediscover the entire project decomposition for every code-generation call.

---

## 17.3 Implementation units

An executable work item may modify multiple related files.

Example:

```text
TASK-021

Authentication backend

Affected implementation:

src/model/User
src/repository/UserRepository
src/service/AuthService
src/api/AuthController
```

These can be generated or modified together when context and model limits allow.

Functions are implementation details and should not automatically be separate work items or API calls.

---

## 17.4 Large files

A final file may be constructed through several iterations:

```text
iteration 1 -> repository state
iteration 2 -> repository state
iteration 3 -> repository state
...
iteration N -> final file
```

The repository stores the accumulated implementation state.

---

## 17.5 Iterative enhancement

Every implementation iteration:

1. Read current repository state.
2. Read only relevant current files.
3. Build bounded context.
4. Request the next coherent implementation change.
5. Parse the response.
6. Write complete resulting files.
7. Verify the change.
8. Continue if additional implementation is required.

---

# 18. Complete-File Rule

When modifying an existing file, the preferred model response is:

```text
## FILE: relative/path/File.java
```

followed by the complete resulting file.

The model should not return arbitrary partial fragments that the orchestrator cannot safely merge.

Patch/diff generation can be added later as a separate capability.

---

# 19. Context Management

Context is divided into:

```text
Global context

  - normalized requirements
  - architecture/repository summary
  - dependency summary
  - relevant workflow state

Work-item context

  - current work item
  - acceptance criteria
  - dependencies
  - relevant files
  - current implementation state
  - relevant verification/test failures
```

The generator must enforce a bounded context budget.

Exclude irrelevant:

- `.git`;
- `.ox2` internal implementation noise;
- virtual environments;
- dependency caches;
- build output;
- generated artifacts;
- unrelated source files.

Only required `.ox2` state should be included.

---

# 20. Verification and Correction Loop

```text
Implementation
      |
      v
Static checks
      |
      v
Tests
   +--+--+
   |     |
 PASS   FAIL
   |     |
   v     v
next   diagnose
         |
         v
     correction
         |
         +----> implementation
```

Failures must produce actionable context.

All correction loops must have configurable maximum iterations.

Verification answers:

> Does this implementation satisfy the work item's acceptance criteria?

Tests answer:

> Does the software actually behave correctly when executed?

Code should move to `implemented/` only after the required verification succeeds.

---

# 21. Error Handling

Provider adapters should normalize failures into categories such as:

```text
AUTHENTICATION
RATE_LIMIT
TIMEOUT
INVALID_REQUEST
MODEL_NOT_FOUND
SERVICE_UNAVAILABLE
UNKNOWN
```

Retryable failures may use configured retry/fallback behavior.

Non-retryable errors should fail fast.

For each provider attempt, logs should include:

```text
provider
model
duration
result
error category
fallback decision
```

Sensitive prompt data and credentials must not be logged indiscriminately.

A provider response containing no usable implementation is not considered successful implementation.

---

# 22. Performance Strategy

The architecture is specifically designed to avoid:

```text
entire README
+
entire repository
+
all previous responses
        |
        v
one huge API request
```

Instead:

```text
requirements
      |
      v
bounded reconciliation/planning
      |
      v
adaptive executable work item
      |
      v
bounded implementation
      |
      v
repository update
      |
      v
bounded verification
```

Do not introduce artificial delays after successful calls.

Rate limiting should be provider-specific and configuration-driven.

Retries should use sensible backoff.

---

# 23. Repository Isolation and Safety

The orchestrator may operate on many unrelated application repositories:

```text
app-orchestrator

    +--> project-A
    +--> project-B
    +--> test-ox2
    +--> production-project
```

It must not assume one language, framework, build system, or repository layout.

Generated paths must be resolved and validated so that:

- `..`;
- absolute paths;
- unsafe symlinks;
- path traversal;

cannot escape the target repository.

---

# 24. Git Strategy

The orchestrator repository and target application repositories are independent.

Development uses feature branches:

```text
main
 |
 +-- feature/incremental-code-generation
```

The orchestrator should not manipulate Git automatically unless Git execution is explicitly enabled by the workflow.

---

# 25. Observability

For every provider call record, where available:

```text
timestamp
agent/workflow
provider
model
request duration
success/failure
error category
retry/fallback
token usage
```

For each executable work item:

```text
work item id
parent id
requirement ids
revision
status
dependencies
files changed
verification result
duration
provider/model
```

For incremental generation:

```text
iteration
files changed
verification result
duration
provider/model
```

This is important for diagnosing provider timeout/fallback behavior and measuring API efficiency.

---

# 26. Testing Strategy

## Unit tests

Cover:

- provider error classification;
- response parsing;
- safe path handling;
- work-tree planning;
- recursive decomposition boundaries;
- maximum depth handling;
- state transitions;
- requirement reconciliation;
- dependency/impact analysis;
- artifact persistence.

## Integration tests

Cover:

- provider registry;
- agent/provider routing;
- workspace operations;
- incremental generation;
- requirement reconciliation;
- pending/implemented state;
- state persistence.

## End-to-end tests

Use an independent target repository such as `test-ox2` containing a substantial README and requiring meaningful multi-file implementation.

The end-to-end test should measure:

- total duration;
- API calls;
- provider/model used;
- fallback count;
- work items created;
- work items implemented;
- files written;
- build result;
- test result;
- final verification result.

API-call count is an important performance metric.

---

# 27. Calculator Stress Test

The calculator project is a deliberate incremental-generation stress test.

The specification is large enough to require multiple implementation work items and includes UI, calculation engine, state, formatting, keyboard input, error handling, tests, and documentation.

Expected conceptual flow:

```text
README
  |
  v
requirements
  |
  v
repository analysis
  |
  v
workflow planning
  |
  v
adaptive work tree
  |
  +--> project setup
  +--> calculator engine
  +--> state
  +--> formatting
  +--> Swing UI
  +--> keyboard support
  +--> tests
  +--> documentation
  |
  v
verification
  |
  v
build
  |
  v
tests
  |
  v
complete calculator
```

The important acceptance criterion is not simply that an AI can generate a calculator.

It is that the orchestrator can construct a coherent multi-file application from a large specification while:

- keeping individual AI API requests bounded;
- avoiding unnecessary planning calls;
- recursively decomposing work;
- persisting work state;
- recovering from failures;
- continuing incrementally.

---

# 28. Security Architecture

Credential flow:

```text
shell environment
      |
      v
provider adapter
      |
      v
AI API
```

Never:

```text
source code -> committed API key
```

Never place credentials in:

- prompts;
- artifacts;
- logs;
- test fixtures;
- README files;
- commits.

The orchestrator should also avoid exposing private repository contents to a provider when those contents are not required for the current work item.

---

# 29. Extensibility

The design must allow future providers without changing agent logic.

Examples:

```text
OpenAI
Anthropic
Mistral
Ollama
vLLM
```

Future logical workflows may include:

```text
architecture
database
migration
performance
accessibility
ui_visual
release
deployment
```

Future execution adapters may include:

```text
shell
git
build
test
browser
container
static analysis
dependency scanner
```

These should be adapters/workflows, not hard-coded into provider logic.

The architecture should avoid class proliferation as new capabilities are introduced.

---

# 30. Non-Goals

The initial architecture does not attempt to:

- build an entire large project in one model request;
- permanently depend on one AI provider;
- store API keys in source code;
- guarantee identical AI output on every run;
- trust generated code without verification;
- manipulate arbitrary files outside the target repository;
- replace normal build/test/security tooling;
- create a separate AI agent/class for every planning level;
- recursively decompose indefinitely;
- regenerate the entire project for every requirement change.

---

# 31. Definition of Done

The architecture is operational when:

1. Providers implement the common provider interface.
2. Credentials come only from environment variables.
3. Agents/workflows are provider-independent.
4. Provider routing is configuration-driven.
5. Repository state is available to workflows.
6. `.ox2` state is persisted.
7. Requirements can be normalized and tracked.
8. Requirements can be reconciled when the README changes.
9. Work can be represented as a recursive work tree.
10. Work can be decomposed adaptively rather than through a rigid hierarchy.
11. Recursive decomposition is bounded to approximately 2–3 levels.
12. Oversized work at the maximum depth causes user intervention rather than unlimited decomposition.
13. Executable work items can be implemented independently.
14. Functions and classes do not automatically become separate API calls.
15. Large requirements can be implemented incrementally.
16. Existing functionality is preserved unless intentionally changed.
17. Only affected implemented work returns to `pending` after requirement changes.
18. Work maintains requirement/dependency traceability.
19. Generated paths are sandboxed to the target repository.
20. Provider failures can fall back according to configuration.
21. Incremental retries/iterations are bounded.
22. Verification/test failures can feed correction loops.
23. Completed work moves to `implemented/` only after required verification.
24. The generated project can be built and tested.
25. The workflow is observable through logs and `.ox2` artifacts.
26. API-call count and provider usage can be measured.

---

# 32. Long-Term Architectural Direction

```text
                         +----------------------+
                         |      CLI / API       |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         |    Orchestrator      |
                         |      Pipeline        |
                         +----------+-----------+
                                    |
             +----------------------+----------------------+
             |                      |                      |
             v                      v                      v
       Requirements          Repository/Workspace    Configuration
             |                      |                      |
             +----------------------+----------------------+
                                    |
                                    v
                         +----------------------+
                         |   .ox2 Project State |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Requirement /        |
                         | Reconciliation       |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Workflow / Planner   |
                         +----------+-----------+
                                    |
                                    v
                         +----------------------+
                         | Recursive Work Tree  |
                         +----------+-----------+
                                    |
                         +----------+----------+
                         |                     |
                  composite work          executable work
                         |                     |
                         |                     v
                         |             +---------------+
                         |             | Implementation |
                         |             +-------+-------+
                         |                     |
                         |                     v
                         |             +---------------+
                         |             | Verification  |
                         |             +-------+-------+
                         |                     |
                         +---------------------+
                                               |
                                               v
                                        Target Repository
                                               |
                                               v
                                             Tests
                                               |
                                               v
                                             Docs
                                               |
                                               v
                                            Commit
```

## Core Architectural Decisions

> **AI models provide intelligence; the orchestrator provides state, decomposition, persistence, routing, iteration, repository control, and verification.**

> **Work decomposition is recursive and adaptive rather than a rigid Requirement → Functionality → Task → Subtask → Function hierarchy.**

> **The Workflow Agent decides where decomposition should stop, subject to a maximum depth of approximately 2–3 levels.**

> **If functionality remains too large at the maximum depth, the orchestrator asks the user to split it rather than creating deeper and deeper abstractions.**

> **Functions and classes are implementation details, not automatically separate orchestration units or API calls.**

> **One planning/reconciliation call should produce as much useful planning information as possible. AI calls are reserved primarily for reasoning and code generation.**

> **`.ox2` is the persistent orchestration state of the target project. `pending/` represents work requiring implementation or revision; `implemented/` represents verified completed work.**

> **When requirements change, the orchestrator performs impact analysis and returns only affected work to `pending`; unaffected implemented work remains untouched.**

> **The architecture should prefer recursion, data-driven workflows, composition, and deterministic orchestration over an ever-growing collection of specialized classes.**

That separation is the foundation of the project and must be preserved as new providers, models, workflows, tools, and execution capabilities are added.