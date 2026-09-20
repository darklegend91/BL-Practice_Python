# LLM Fit Advisor — production architecture and delivery guide

Date: 2026-09-19

Status: proposed architecture and delivery guide; implementation pending.

## 1. Product and constraints

Build a company application that helps people and teams decide whether to run a downloadable language model on their own hardware or purchase a hosted chat subscription. Recommendations must explain suitability, costs, assumptions, evidence, and uncertainty.

The system uses fixed-choice questions, numeric values, Pydantic validation, a PostgreSQL catalog, and ordinary Python calculations. PostgreSQL is the system of record. JSON remains useful for imports, exports, and selected database snapshots.

Confirmed constraints:

- Our own HTTP API is allowed; external data and model API integrations are excluded.
- The application performs no LLM inference and calls no LLM service.
- Crawl4AI collects public source pages. Application extractors must not use CSS selectors, XPath, or regex.
- Users answer structured questions; the application does not interpret free-text prompts.

Recommended architecture: one Python codebase, with separate API and crawler processes and one PostgreSQL database.

Important design assumption: editors enter structured specifications and prices from collected pages and reviewers approve them. This is a proposed operating model, not a previously confirmed user preference. Automatic crawling does not automatically produce verified product records. If fully automatic extraction becomes mandatory, the extraction restrictions or supported source formats must be revisited.

The extraction restriction applies to application code. Crawl4AI still uses its normal browser and HTML-to-Markdown internals; this design makes no claim that third-party dependencies never internally use selectors or regex.

## 2. What the product compares

| Candidate | Decision covered | Required evidence |
| --- | --- | --- |
| Existing local computer | Can the user run a suitable model with current hardware? | Hardware inventory, compatible runtime, model variant, memory and capability evidence |
| Local upgrade | Is a specific upgrade worthwhile? | Incremental components, compatibility, local prices, power assumptions |
| New local machine | Is purchasing a complete system justified? | Complete bill of materials, regional prices, setup and operating costs |
| Hosted subscription | Does a plan meet the user's workload and constraints? | Regional price, billing cycle, seat policy, features, limits, current terms |

A hosted subscription is evaluated as the documented product. It is not assumed to provide programmatic access or unrestricted usage. If a user requires application integration and no supported candidate meets that need, return a clear unsupported or insufficient-data result.

Keep downloadable model variants, proprietary model descriptions, and commercial plans separate. A proprietary model's advertised capability does not establish that every subscription includes it. Preserve the difference between open weights and an open-source license, including commercial-use restrictions.

Initial supported workload: text inference and text-assistant subscriptions. Training, fine-tuning, distributed multi-GPU configurations, and automated model execution are outside the first release. CPU and system RAM are captured for compatibility; recommend CPU-only inference only when suitable evidence exists.

## 3. Company features and rollout priority

| Area | First usable release | Required before external company users | Expansion after measured demand |
| --- | --- | --- | --- |
| Questionnaire | Options, units, numeric ranges, transparent presets | Saved versions and accessibility review for any UI | Department-specific presets |
| Catalog | Hardware, model variants, plans, manually entered regional prices | Evidence, review, revision history, freshness policy | More manufacturers and markets |
| Recommendations | Feasibility checks, costs, reasons, alternatives | Reproducible decisions, uncertainty handling, regression cases | Optional local-plus-subscription comparison |
| Team work | One workspace with saved scenarios | Multiple workspaces, roles, ownership and access tests | Procurement approval chains |
| Crawling | Registered URLs, manual refresh, stored Markdown | Durable jobs, resource limits, safe network access, change review queue | Controlled category-page discovery |
| Reporting | Detailed result and JSON export | CSV export, audit trail, reproducible report versions | Budget reports and department comparisons |
| Operations | Local development and staging | Backups, restore drill, monitored jobs, deployment rollback | Availability upgrades driven by service targets |

Additional useful features:

1. Hardware inventory shared within a workspace, including whether the hardware is dedicated or already used for other work.
2. Side-by-side scenarios: existing GPU versus upgrade, 6 versus 24 months, different electricity prices, and different setup-time budgets.
3. Watchlists for selected products and plans; show change notices inside the application.
4. Price history with separate retailer offers, availability, taxes, and currency.
5. A review dashboard for changed pages, failed crawls, stale records, disputed claims, and missing evidence.
6. Recommendation history with an explicit refresh action. Refresh creates a new result instead of altering the old one.
7. User feedback such as “setup took longer” or “speed was insufficient,” stored separately from verified catalog evidence.
8. Organization defaults for region, budget, currency, electricity rate, and permitted deployment choices.

## 4. Structured input contract

Use stable option identifiers in the API, with separate human-readable labels. Store `coding`, not an option's current display position such as `1`.

| Input | Type and example choices | Reason |
| --- | --- | --- |
| Workload | coding, studying, writing, document analysis | Select required capabilities and suitable evidence |
| Access requirement | interactive use, application integration | Prevent incompatible product recommendations |
| Usage level | light, medium, heavy, custom | Provide a simple entry path |
| Work volume | requests/day; short, medium or long responses | Assess plausible capacity; not an exact conversion to subscription limits |
| Context requirement | short conversation, long document, custom tokens | Check documented context support and memory implications |
| Seats and concurrency | positive integer values | Distinguish team seats from simultaneous local sessions |
| Planning period | integer months, initially 1–60 | Compare total costs over a defined period |
| Budget | upfront and monthly amounts | Distinguish affordability from long-term savings |
| Location | supported region and currency | Select applicable offers and plan availability |
| Existing equipment | saved inventory or explicit GPU, CPU, RAM and storage values | Calculate only necessary purchases |
| Local operating time | active and idle hours/day, or an explicit preset | Estimate whole-system electricity use |
| Electricity tariff | money per kWh | Calculate operating cost |
| Setup preference | beginner, comfortable, experienced | Check acceptable setup effort |
| Setup allowance | hours initially and hours/month for maintenance | Include the user's time constraints |
| Constraints | offline required, external processing allowed, commercial use | Apply hard eligibility rules |
| Preference | lowest cash cost, least setup, offline control | Order eligible choices predictably |

Pydantic models should reject unsupported choices, unknown fields, negative money, non-finite numbers, invalid counts, mixed currencies without a conversion record, and active-plus-idle time above 24 hours/day. Missing values remain unknown. A missing price or electricity tariff is never silently interpreted as zero.

Normalize numeric form input at the boundary, then validate it deliberately; reject booleans supplied as numeric values. Display preset assumptions before computing a result. Every result records the expanded values and preset version. Pydantic's strict mode helps control coercion but does not replace domain validation. [Pydantic strict-mode documentation](https://docs.pydantic.dev/latest/concepts/strict_mode/).

An API response can return `needs_input` with specific missing field names. The caller can then display additional option/value questions. This needs no conversation model or natural-language interpretation.

## 5. Collection, review, and catalog publication

### Collection

Register approved sources with a URL, owner, category, allowed domains, refresh interval, maximum page size, timeout, and crawl permission notes. Manufacturers supply specifications; retailers supply offers; publishers supply model information; provider plan pages supply subscriptions and terms.

Crawl4AI produces readable Markdown, which can be stored with its URL, timestamps, status, content hash, and crawler version. Its default Markdown generator supports this collection step without an LLM extraction strategy. [Crawl4AI Markdown documentation](https://docs.crawl4ai.com/core/markdown-generation/).

Hash normalized text to detect changes and use Python `difflib` to prepare a textual review. A changed page indicates a need to review; it does not prove that a particular price changed. A successful unchanged fetch also does not independently verify every structured claim.

Start with configured URLs. Later discovery can inspect Crawl4AI's returned links and parse sitemaps with a standard XML parser. Discovered URLs become reviewable candidates and must remain within approved domains, depth and page-count budgets.

### Review and publishing

1. The worker saves a new immutable page snapshot or records an unchanged fetch.
2. An editor enters or revises typed catalog fields using options and values.
3. Each material claim links to its source snapshot and a short supporting excerpt.
4. Pydantic and database constraints validate units, ranges, identity and required fields.
5. A separate reviewer approves publication for shared production data.
6. Publication creates an immutable catalog revision and updates the current-revision pointer in one transaction, together with its audit event.

Workflow: `draft → pending_review → published`, with `rejected` and `superseded` outcomes. Production users cannot recommend draft records. Prevent editors from approving their own critical price, license or capability changes; a small organization therefore needs at least two authorized people for this workflow.

Proposed freshness defaults: prices, stock and plan limits are due for review after 7 days; technical specifications and model metadata after 30 days. Administrators can shorten them by source. Display fetch age and review age separately. Exclude stale critical facts from a confident recommendation unless the user explicitly chooses an estimate using stale data; retain the warning in the saved result.

Failed collection preserves the last published version and creates an operational issue. Contradictory sources create a review task. Do not overwrite one retailer's price with another retailer's price under the same identity.

## 6. Recommendation engine

The core interface is a pure Python function over a validated scenario, an immutable catalog snapshot, and a versioned policy. It returns a typed result. Network calls, database writes and browser work happen outside that function.

Processing sequence:

1. Validate inputs and expand explicit presets.
2. Load a consistent set of approved catalog revisions and evidence.
3. Generate a bounded set of local configurations and applicable subscription plans.
4. Apply hard constraints: region, offline access, commercial-use permission, capability, memory, budget, and required access type.
5. Classify candidates as feasible, infeasible, or uncertain. Unknown evidence does not count as a successful constraint check.
6. Calculate cash cost, optional time-valued cost, and sensitivity cases.
7. Rank feasible choices by the user's selected priority, using documented tie-breakers. Keep uncertain choices separate.
8. Return the selected choice, alternatives, exclusion reasons, assumptions, and evidence.

Use named rule identifiers, for example `OFFLINE_REQUIRED`, `VRAM_INSUFFICIENT`, `LICENSE_UNVERIFIED`, `PRICE_STALE`, and `SUBSCRIPTION_LIMIT_UNKNOWN`. Generate readable explanations from templates with actual values. Keep policy changes in reviewed Python code and versioned configuration; do not accept executable rules from administrators.

### Hardware and capability checks

- Link a model recommendation to a specific revision, quantization format and supported runtime.
- Estimate total memory from weights, context-dependent cache and runtime overhead. Parameter count alone does not establish required memory.
- Use declared GPU VRAM and system RAM as different resources. Do not add them together as if they provide equivalent performance.
- Treat CPU offload, CPU-only execution, long context and concurrency as separate configurations that need evidence.
- Store published benchmarks with model revision, quantization, GPU, runtime, context length, concurrency, date and source. Mark mismatched measurements as approximate.
- A model that fits into memory is not automatically fast enough or good enough for a task. Report performance or quality as unknown where evidence is inadequate. [Hugging Face memory-estimation caveats](https://huggingface.co/docs/accelerate/main/usage_guides/model_size_estimator).

For capability, record task-specific supported/unsupported/unknown claims backed by evidence. Do not invent a universal “intelligence score.” A documented offline model can be a feasible privacy choice while remaining uncertain for the user's task quality threshold.

### Cost calculation

Use `Decimal` in Python and an appropriate PostgreSQL `NUMERIC` precision for money. Include currency, units, date and source. PostgreSQL provides exact numeric types suitable for values where rounding behavior matters. [PostgreSQL numeric types](https://www.postgresql.org/docs/current/datatype-numeric.html).

For each comparison month:

```text
energy_kWh = days × (active_watts × active_hours_per_day
                    + idle_watts × idle_hours_per_day) / 1000
energy_cost = energy_kWh × tariff_per_kWh

local_cash_total = required_new_hardware + setup_cash_expenses
                   + sum(energy_cost + recurring_cash_expenses)

subscription_cash_total = actual billed plan commitments
                          + known taxes and required extras

optional_time_cost = (setup_hours + total_maintenance_hours) × user_hourly_value
```

Use whole-system operating power. A GPU's advertised power limit is not a measured whole-system consumption figure. If measurements are unavailable, use clearly labeled low/base/high assumptions that the user can change.

Existing hardware has zero new purchase cost in the incremental-cash view. Show optional economic allocation or resale assumptions separately so they cannot silently change the cash comparison. New-machine candidates include necessary RAM, storage, PSU and other parts; a GPU price alone is not a complete system price.

Apply each plan's actual billing cycle, minimum seats, commitments and regional availability. A twelve-month commitment is not silently prorated for a two-month comparison. Persist manually reviewed currency conversions with date and source; never mix currencies or call an exchange-rate API.

Find break-even by evaluating cumulative cash outlay month by month within the user's horizon. Report no crossover when applicable and identify later reversals, including annual renewal steps. Compare only options meeting the same required capabilities. Show the conclusion for low/base/high usage and energy assumptions; if the winner changes, label the recommendation sensitive to those assumptions.

### Result contract

Every result includes:

- Status: `recommended`, `needs_input`, `insufficient_evidence`, or `no_feasible_option`.
- Selected candidate, alternatives, and ruled-out candidates with reason codes.
- Upfront cost, recurring schedule, total horizon cost, optional time cost, currency and rounding policy.
- Memory/capability evidence, expected setup effort, and performance uncertainty.
- Break-even details and sensitivity outcomes.
- Source links, reviewed dates, stale or missing fields, and an evidence-quality label.
- Scenario revision, catalog revision IDs, preset and policy versions, application version, creation timestamp and calculation inputs.

Evidence-quality labels describe freshness and completeness, not a statistical probability of being correct. Store calculation inputs and outputs immutably; retain the application release artifact so past decisions can be reproduced. Viewing a historical result must not recompute it against today's prices.

## 7. Application architecture

Use a modular monolith: one repository and release, with modules for identity, catalog, collection, review, scenarios, recommendations and reporting. Deploy the API and crawler worker as separate processes so browser work cannot block user requests.

| Component | Responsibility | Suggested tools |
| --- | --- | --- |
| HTTP service | Validation, authorization, catalogs, scenarios and results | FastAPI, Uvicorn, Pydantic |
| Domain engine | Eligibility, memory estimates, costs and explanations | Python standard library, Decimal |
| Persistence | Transactions and relational queries | SQLAlchemy with Psycopg |
| Schema changes | Reviewed database upgrades | Alembic |
| Collector worker | Bounded page collection and snapshot storage | Crawl4AI, asyncio |
| Scheduler | Enqueue due refreshes with deduplication | Small Python process or deployment timer |
| Database | Catalog, jobs, snapshots, identity and audit | PostgreSQL |
| Verification | Unit, integration and contract testing | pytest and real PostgreSQL in isolated tests |

FastAPI supports Pydantic request models and generated OpenAPI documentation. Give each request or worker unit its own SQLAlchemy session; do not share a session across concurrent tasks. Use explicit transaction boundaries and close sessions promptly. [FastAPI request models](https://fastapi.tiangolo.com/tutorial/body/), [SQLAlchemy sessions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html). Review and test migrations before applying them. [Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).

Proposed eventual code organization:

```text
app/
  main.py
  config.py
  api/             # versioned HTTP routes and authorization
  schemas/         # Pydantic request, catalog and result contracts
  db/              # SQLAlchemy mappings, sessions and queries
  catalog/         # source evidence, review and publication
  collection/      # Crawl4AI adapter, discovery and page snapshots
  engine/          # feasibility, costing, ranking and explanations
  services/        # scenario, recommendation and reporting workflows
  workers/         # durable job processing and scheduling
migrations/
tests/
  unit/
  integration/
  contracts/
  fixtures/
docs/
```

No Redis, separate search engine or message broker is needed for the proposed initial workload. PostgreSQL performs filtered catalog queries and job coordination. Revisit infrastructure only after measurements show a concrete bottleneck.

## 8. PostgreSQL data model

Use typed relational columns for identity, money, status, dates and relationships. Use JSONB for validated variant attributes, scenario/result snapshots and structured audit details. PostgreSQL remains authoritative; JSON files are import/export artifacts.

| Table or related tables | Important fields and behavior |
| --- | --- |
| `users`, `sessions` | Local identities, password hash, token digest, expiry, revocation |
| `organizations`, `memberships` | Workspace ownership, user-role membership, unique organization/user pair |
| `sources` | Approved URL, allowed hosts, category, refresh policy, enabled state |
| `crawl_jobs` | State, source ID, run-after time, deduplication key, attempts, lease token and expiry |
| `source_snapshots` | Source ID, fetch time, final URL, content hash, bounded Markdown text, version |
| `catalog_items` | Stable identity and kind: hardware, model or plan; current published revision |
| `catalog_revisions` | Immutable typed/validated attributes, schema version, author, publication and supersession status |
| `evidence_claims` | Revision, field name, value, snapshot, excerpt, review status and review date |
| `price_observations` | Revision/offer identity, seller, region, currency, amount, tax status, billing interval, availability, evidence |
| `plan_model_access` | Plan revision to model revision, access conditions and supporting evidence |
| `benchmark_observations` | Exact tested configuration, metrics, workload, date and evidence |
| `reviews` | Draft revision, reviewer, decision, notes and timestamp |
| `inventory_items` | Organization-owned configuration, quantities, purchase status and ownership |
| `scenario_revisions` | Organization, creator, immutable validated input and schema/preset versions |
| `recommendation_runs` | Scenario, policy/app versions, immutable input/output snapshots and timestamps |
| `recommendation_evidence` | Run-to-revision and observation links for provenance |
| `audit_events` | Actor, organization when relevant, action, target, timestamp and redacted change details |
| `idempotency_keys` | Organization, route, key digest, request hash, outcome and expiry |

Store small bounded Markdown snapshots directly in PostgreSQL `TEXT` initially. Set a maximum uncompressed page size and a retention policy; retain snapshots referenced by published evidence or saved decisions. Separate large artifact storage can be considered later if volume warrants it.

Database requirements:

- UUID identifiers, foreign keys, explicit uniqueness rules and nonnegative amount/count checks.
- UTC `TIMESTAMPTZ` timestamps, explicit units, finite numeric values and documented decimal precision.
- Organization identity on every private business record, with compound foreign keys or equivalent checks preventing cross-organization relationships.
- Index source fetch history, due jobs, catalog kind/status, region/currency offers, and organization/result creation time.
- Use optimistic revision checks when editing drafts; return a conflict if another editor has changed the record.
- Publish a revision, its claims and audit event atomically. Keep recommendation evidence references stable across publication changes.
- Obtain a consistent database snapshot for recommendation input selection, then persist the exact selected revisions. Use a repeatable-read transaction or equivalent single-version selection strategy.
- Prevent deletion of catalog evidence referenced by historical results; retire or supersede records instead. Handle private scenario deletion through a documented retention policy.

Apply application authorization and PostgreSQL row-level security to tenant-private data. Use a runtime role that is not a table owner, superuser, or `BYPASSRLS` role; set verified organization context transaction-locally and fail closed when absent. Keep migration credentials separate. RLS does not protect against privileged bypasses, so test roles and connection reuse explicitly. [PostgreSQL row security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

## 9. Own HTTP API

Expose versioned endpoints. Request bodies and responses use explicit Pydantic schemas; never expose internal database objects directly.

| Method and path | Purpose | Access |
| --- | --- | --- |
| `POST /v1/auth/login`, `POST /v1/auth/logout` | Create or revoke a local session | Local user |
| `GET /v1/questionnaire` | Choices, units, ranges and preset version | Workspace member |
| `GET /v1/catalog/hardware` | Browse approved hardware | Workspace member |
| `GET /v1/catalog/models` | Browse approved model variants | Workspace member |
| `GET /v1/catalog/plans` | Browse applicable subscription plans | Workspace member |
| `GET /v1/catalog/items/{id}/history` | Review published history and evidence | Authorized member |
| `POST /v1/scenarios` | Save validated option/value inputs | Analyst |
| `POST /v1/recommendations` | Calculate and save a recommendation | Analyst |
| `GET /v1/recommendations/{id}` | Retrieve the saved result | Same-workspace authorized member |
| `GET /v1/recommendations/{id}/export` | JSON or CSV export | Same-workspace authorized member |
| `POST /v1/admin/sources` | Register an approved source | Platform catalog administrator |
| `POST /v1/admin/crawl-jobs` | Queue a registered source refresh | Catalog editor |
| `GET /v1/admin/crawl-jobs/{id}` | Inspect collection status | Catalog operator |
| `POST /v1/admin/catalog/drafts` | Create a typed draft with evidence | Catalog editor |
| `POST /v1/admin/catalog/drafts/{id}/submit` | Request review | Catalog editor |
| `POST /v1/admin/catalog/drafts/{id}/approve` | Approve and publish | Independent catalog reviewer |
| `GET /health/live`, `/health/ready` | Process and dependency health | Minimal operational response |

Add organization/member management and inventory endpoints as part of the team phase. Platform catalog roles are separate from workspace roles: a customer workspace administrator cannot publish shared catalog prices.

Contract rules:

- `201` for created resources and `202` for accepted crawl jobs. The recommendation path never waits for a live crawl.
- Bounded catalog pagination and filters; stable ordering and maximum page size.
- Structured errors with `code`, `message`, field errors and a correlation ID. Use `422` for invalid input, `401` for missing/invalid authentication, `403` for forbidden actions and `409` for conflicts. Mask resource existence where needed across organizations.
- A valid calculation with no suitable candidates returns a typed domain outcome, not an HTTP server failure.
- Idempotency keys for crawl enqueueing and saved calculations. Scope them to organization and route; the same key and request replays the saved outcome, while a different request with that key is a conflict. A proposed retention window is 24 hours.
- Rate limits and request-size limits on login, writes, exports and expensive comparisons.

## 10. Durable crawler jobs

Use a PostgreSQL job table and a worker loop. Claim an eligible row with a short transaction, write a unique lease token and expiry, then commit before starting the browser. PostgreSQL documents `SKIP LOCKED` as appropriate for queue-like access; it is not a general-purpose consistent-reading mechanism. [PostgreSQL locking behavior](https://www.postgresql.org/docs/current/sql-select.html).

Jobs move through `queued → running → succeeded`, with retry scheduling and a final `failed` state. A cancellation state may be added when user-triggered cancellation is implemented.

- Bound browser concurrency and per-domain request frequency. Start with a small configurable limit and benchmark memory use.
- Retry transient failures with bounded backoff. Treat invalid configuration and prohibited sources as permanent failures.
- Heartbeat long jobs; reclaim expired leases after a worker crash.
- Every completion/update must match the current lease token so a stale worker cannot overwrite a new attempt.
- Treat execution as at least once. Deduplicate snapshot writes and downstream review tasks with database constraints and transaction-safe operations.
- Use a uniqueness key based on source and schedule slot to prevent multiple schedulers enqueueing the same refresh.
- Preserve attempt history, timings and errors without logging credentials or private content.
- Close browser resources on timeout and shutdown. Do not hold database locks while rendering pages.

## 11. Security and access

Use local accounts and maintained password-hashing/session libraries. Hash passwords with Argon2id. Issue high-entropy opaque session tokens, store only their digests, and enforce expiration and revocation. If a browser interface uses cookies, require secure, HttpOnly cookies and CSRF protection for mutations. Add locally verifiable MFA for privileged accounts before broad external use.

Workspace roles: owner manages membership; analyst manages scenarios and recommendations; viewer reads permitted results. Platform catalog roles: editor prepares claims, reviewer approves, administrator controls sources. Enforce authorization in service functions as well as HTTP routes so worker and import paths cannot bypass it.

Crawler protections are mandatory because browser requests originate from company infrastructure. Accept registered source IDs, restrict permitted schemes and destinations, validate redirects, and enforce network egress controls against loopback, private, link-local and cloud-metadata destinations. Cover browser subrequests and DNS changes, not only the initial URL. Isolate browser traffic from database/admin networks; allow the worker's application-side database connection through a separate controlled path. [OWASP SSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).

Additional controls:

- Respect site crawl policies, permission constraints and rate limits; do not bypass authentication, paywalls or anti-bot challenges.
- Treat collected Markdown/HTML as untrusted content. Render it as escaped text or sanitized Markdown; never execute embedded scripts in the review application.
- Bind SQL parameters; never interpolate input into SQL statements. [Psycopg parameter documentation](https://www.psycopg.org/psycopg3/docs/basic/params.html).
- Store secrets outside source control; use separate credentials for runtime, jobs and migrations and rotate them.
- Keep account secrets and private scenario details out of normal logs.
- Audit membership changes, catalog publication, imports and policy releases. Restrict update/delete privileges on audit rows; export protected operational archives under the retention policy.
- Use explicit export authorization. Protect CSV output from formula injection in user-controlled string cells.
- Provide account and scenario deletion procedures compatible with documented audit and evidence retention.

## 12. Deployment, monitoring, and recovery

Development can run the application, worker and PostgreSQL through a local container composition. Production uses the same release artifact with independent API/worker processes, a supervised scheduler, TLS termination, persistent PostgreSQL storage and protected backups. Size machines from staging measurements; browser concurrency is the principal initial resource control.

Keep development, staging and production databases separate. Pin tested dependency versions, including the browser installation paired with Crawl4AI, and record them in the release. Run reviewed migrations as a controlled deployment step. Prefer additive schema changes so the previous application release remains usable during rollback.

Observe request latency/errors, connection-pool exhaustion, queue age, worker heartbeat, page failures by source, review backlog, stale catalog coverage and recommendation outcomes. Use structured logs with correlation/job IDs and internal operational alerts. A healthy API does not imply a fresh catalog; show those states separately.

Proposed launch targets, to validate rather than advertise as existing guarantees:

| Target | Initial acceptance test |
| --- | --- |
| Recommendation latency | p95 below 1 second for at most 200 candidate configurations and 20 concurrent recommendation requests on the documented staging machine |
| Bounded memory | A two-hour configured-concurrency crawl soak completes without leaking browser processes or growing memory without bound |
| Worker recovery | A killed worker's expired job is safely reclaimed without duplicate published revisions |
| Availability objective | 99.5% monthly for the authenticated recommendation service; requires measurement and operational ownership |
| Recovery point objective | At most 1 hour of database loss, supported by monitored archive cadence |
| Recovery time objective | Restore service within 4 hours in a timed rehearsal |

Configure PostgreSQL base backups and WAL archiving to meet recovery targets. Encrypt backups, keep a copy outside the application's failure domain and test restoration into an isolated environment. A daily SQL dump alone does not meet a one-hour recovery-point target. PostgreSQL documents dumps, physical backups and continuous archiving as distinct backup approaches. [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html).

Maintain short runbooks for failed crawls, a bad catalog publication, database outage, excessive review backlog, secret rotation, restore, and rollback. Assign a named owner for catalog operations and a named owner for the service. Manual curation capacity limits catalog expansion; measure review time per source before increasing coverage.

## 13. Verification strategy

Unit tests should exercise business outcomes, including:

- Existing hardware versus new purchase and complete-system costs.
- Monthly versus annual billing and minimum seat commitments.
- Currency/rounding rules, unknown prices, stale evidence and invalid numeric inputs.
- Zero operating savings, no break-even, crossover reversals and sensitive outcomes.
- Offline and commercial-use constraints, missing capability evidence and unsupported access requirements.
- Different model variants, context lengths and concurrent sessions; no unsupported pooling of RAM and VRAM.
- Determinism for the same scenario, catalog and policy versions.

Integration tests must run against real PostgreSQL in an isolated test database. Cover migrations, transactions, rollback, tenant isolation and RLS, connection-context reuse, optimistic edit conflicts, immutable histories, lease expiry and stale-worker fencing. Do not substitute SQLite for these tests.

Use saved page fixtures and mocked crawl boundaries for routine tests. Test page-change review behavior without relying on live vendor websites. Any live collection smoke check is explicit, rate-limited and operationally separate from the deterministic suite.

Contract tests check request validation, authorization, pagination, idempotency and typed result/error responses. Security tests include cross-organization object access, unsafe destinations/redirects, malicious Markdown and exports. Run load, recovery and restore exercises before making production readiness claims.

## 14. Build order and completion gates

### Stage 1 — contracts, database and curated catalog

Create the application structure, PostgreSQL migrations, local identity, workspace boundaries, Pydantic contracts and typed catalog CRUD. Seed a small clearly labeled dataset with sources, and implement draft/review/publication.

Done when a reviewer can publish a hardware/model/plan revision and another workspace cannot read private scenarios. No source data should be called verified unless it actually completed review.

### Stage 2 — recommendations using saved data

Implement the questionnaire, scenarios, pure calculation engine, versioned policy, results and JSON/CSV exports. Support existing hardware, a bounded set of upgrades/new machines and applicable subscriptions.

Done when representative decision cases have independently checked calculations and reproduce against frozen catalog versions. Unknown evidence must produce visible uncertainty or a domain outcome, not invented values.

### Stage 3 — collection and catalog maintenance

Add registered sources, the worker, PostgreSQL job queue, Markdown snapshots, change detection, review tasks and freshness checks.

Done when collection failures and worker crashes are recoverable, browser traffic is constrained, and a page change cannot silently publish a price or specification.

### Stage 4 — company operation

Complete role administration, inventory, watchlists, history, audit visibility, backup/restore, monitoring, staging deployment and access/security tests.

Done when the chosen launch targets are demonstrated on documented infrastructure and operators complete a restore and rollback exercise. At that point the system can be evaluated for a controlled production rollout.

### Stage 5 — expand based on actual usage

Expand manufacturers, model families, regions and team workflows only as review capacity and evidence permit. Add supported CPU-only or advanced hardware configurations when trustworthy performance data exists. Keep unsupported scenarios explicit.

## 15. How this relates to the current repository

The repository currently contains synchronous/asynchronous HTTP clients, a Crawl4AI Markdown collector, a regex-based parser, a normalizer, a basic standard-library HTTP server and pytest files. They are useful prototypes; their presence does not establish production readiness.

Reuse the collection boundary and the offline-testing approach. The new catalog workflow takes structured values through Pydantic, so the existing regex parser is not part of the proposed production ingestion path. Introduce the production FastAPI service alongside the learning scripts before deciding which scripts to retire. Convert file-based persistence incrementally behind a database boundary; validate any old JSON import and preserve its original source.

The nested `fastapi-crm-project` is separate from this design. Implementation, dependency installation, database creation and deployment have not been performed as part of writing this guide.
