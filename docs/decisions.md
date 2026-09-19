# Implementation decisions and deviations

This records where the implementation makes a choice the production guide left
open, and where it deviates. It is deliberately short and specific.

## Choices the guide left open

**Workspace context is explicit, never inferred.** A request names its
workspace with `X-Organization-Id`. The guide's team phase assumes multiple
workspaces, and inferring the workspace from a single membership would have to
be removed later. It also interacts badly with row-level security: the
`memberships` table is itself workspace-private, so the membership read runs
under the requested workspace and fails closed when none is named.

**Egress checking is split in two.** `check_url_shape` runs static checks
(scheme, port, embedded credentials, literal address, domain allow-list) and is
used when a source is registered. `check_url` adds name resolution and runs
immediately before a page is fetched. Resolving at registration would block a
briefly unresolvable host for no benefit, because DNS can change before the
page is ever fetched; the check that matters is the one at request time.

**Assumed power puts a candidate in the uncertain group.** The guide requires
labelled low/base/high assumptions when whole-system power is not measured. A
candidate whose power is assumed carries `POWER_ASSUMED` and is ranked
separately from candidates with measured figures, rather than competing with
them on equal footing.

**Login does not validate the email format.** The field is length-bounded but
not format-checked. Login looks an identifier up; rejecting a syntactically
unusual address would both lock out valid accounts and express an opinion about
which addresses exist.

**`FORCE ROW LEVEL SECURITY` is enabled.** Policies apply to the table owner as
well, so a mistaken connection as the owner cannot quietly bypass tenant
isolation. The migration and seed paths set the workspace context explicitly.

## Known gaps against the guide

These are named rather than quietly omitted.

- **No user interface.** The guide's questionnaire and review dashboard are
  served as API contracts only. `GET /v1/questionnaire` returns everything a UI
  would need, and `GET /v1/admin/freshness/*` backs the review dashboard, but
  no pages are rendered. The accessibility review the guide requires before
  external users therefore has nothing to review yet.
- **Stage 4 operations are not demonstrated.** Backups, restore drills,
  monitoring and the launch targets in guide section 12 are documented in
  `runbooks.md` and left as claims to validate, not achievements. No load test,
  soak test or restore rehearsal has been run.
- **Organization and inventory management endpoints are not implemented.** The
  `organizations`, `memberships` and `inventory_items` tables exist and are
  enforced, but membership is managed directly in the database. The guide
  places this in the team phase.
- **Watchlists, price history browsing and user feedback** from guide section 3
  are not implemented. `price_observations` retains history, so the data is
  there; the endpoints are not.
- **Discovery is implemented but not wired into the worker.** Sitemap and link
  discovery are available and tested, but the worker collects only registered
  URLs. The guide places controlled discovery after measured demand.
- **Crawl4AI is an optional extra and unexercised in tests.** The deterministic
  suite uses saved page fixtures, as the guide requires. The Crawl4AI backend
  has no automated coverage; a live collection smoke check remains to be set up
  as an explicit, rate-limited, operationally separate step.
- **Rate limiting is per process.** It bounds one process only. A multi-process
  deployment needs the same limits at the ingress.
- **No MFA.** The guide requires locally verifiable MFA for privileged accounts
  before broad external use. Not implemented.
- **CPU-only inference is modelled but not recommended.** `estimate(...,
  cpu_only=True)` sizes it, and no candidate generation path produces CPU-only
  candidates, because the guide requires evidence before recommending them and
  the sample catalog has none.
