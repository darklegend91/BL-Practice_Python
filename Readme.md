# LLM Fit Advisor

Helps a person or team decide whether to run a downloadable language model on
their own hardware or buy a hosted chat subscription, and explains why.

The application performs **no model inference and calls no external model API**.
It answers from structured questionnaire input and a human-reviewed catalog of
hardware, model variants, subscription plans and prices.

Built to [`docs/production-guide.md`](docs/production-guide.md). Where the
implementation chose between options the guide left open, or falls short of it,
that is recorded in [`docs/decisions.md`](docs/decisions.md).

## What it does

- Takes fixed-choice answers and numbers, validated by Pydantic. No free text
  is interpreted.
- Compares four candidates: the existing computer, a specific upgrade, a new
  machine, and applicable subscription plans.
- Checks memory, context length, licensing, region, access type, budget and
  setup effort, then costs each candidate month by month in `Decimal`.
- Reports break-even, low/base/high sensitivity, every assumption it made, and
  every piece of evidence behind the answer.
- Says **unknown** when the evidence is unknown. An unreviewed value never
  counts as a satisfied requirement.

## Running it

Requires Python 3.12+ and PostgreSQL 14+.

```bash
make install
make db      # creates roles, databases, applies migrations
make seed    # publishes a clearly-labelled sample catalog
make api     # http://localhost:8000/docs
```

Or with containers:

```bash
docker compose up --build
```

Sign in with the seeded analyst account (`analyst@example.invalid`, password
`development-only-password`), then read `GET /v1/questionnaire`, save a scenario
and request a recommendation. Every request needs `Authorization: Bearer <token>`
and `X-Organization-Id: <workspace>`.

The seeded catalog is sample data. It is not reviewed vendor evidence and must
not be used for a real purchase decision.

## Tests

```bash
make test              # everything
make test-unit         # pure engine and schemas, no database
make test-integration  # real PostgreSQL: migrations, RLS, leases, publication
make test-contracts    # the HTTP API end to end
```

Integration and contract tests need a PostgreSQL test database and skip cleanly
without one. SQLite is not substituted: row-level security, lease fencing and
the immutability triggers cannot be represented in it.

Collection tests use saved page fixtures under `tests/fixtures/pages`. Nothing
in the suite reaches a live vendor site.

## Layout

```text
app/
  api/          versioned HTTP routes, dependencies, rate limits
  catalog/      draft-review-publish workflow, snapshot selection, freshness
  collection/   Crawl4AI adapter, saved-page backend, change review, discovery
  db/           SQLAlchemy mappings, sessions, tenant context
  engine/       the pure decision function: memory, feasibility, cost, ranking
  schemas/      Pydantic contracts for input, catalog and results
  security/     Argon2id, opaque sessions, authorization, egress guard
  services/     scenarios, recommendations, exports, idempotency
  seed/         labelled sample catalog
  workers/      durable job queue, crawler worker, scheduler
migrations/     reviewed Alembic revisions
tests/          unit, integration, contracts, fixtures
docs/           the production guide, decisions, runbooks
```

Alongside it, `src/` holds the earlier learning prototypes (synchronous and
asynchronous HTTP clients, a Crawl4AI Markdown collector, a regex parser, a
normalizer and a standard-library HTTP server) with their tests in `tests/`.
Guide section 15 keeps them in place rather than retiring them on day one: the
production ingestion path takes structured values through Pydantic, so the
regex parser is deliberately not part of it. They have their own dependencies
in `requirements-prototype.txt`.

The API and the crawler worker are separate processes from one release
artifact, so browser work can never block a user request.

## How the decision is made

`app/engine/recommend.py` is a pure function of `(scenario, catalog snapshot,
policy)`. It does no I/O, so the same three inputs always give the same result.
Everything that influenced a result — policy version, preset version, catalog
revision identifiers, application version — is stored with it, and a stored
result is never recomputed when it is viewed.

Rules are named. `VRAM_INSUFFICIENT`, `PRICE_STALE`, `LICENSE_UNVERIFIED` and
the rest are enumerated in `app/engine/reasons.py` with the templates that turn
them into sentences with real values in them.

## What it deliberately will not do

- Add GPU VRAM and system RAM together as though they were one pool.
- Treat a missing price or electricity tariff as zero.
- Prorate a twelve-month commitment across a two-month comparison.
- Overwrite one retailer's price with another's.
- Call an exchange-rate API, or mix currencies without a reviewed conversion.
- Publish a catalog change because a page changed.
- Let an editor approve their own price, licence or capability change.
- Invent an "intelligence score", or claim a model is fast enough without a
  benchmark that matches the configuration.
