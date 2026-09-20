# Runbooks

Short operational procedures for the situations the production guide (section
12) names. Each assumes access to the runtime environment and the database.

Named owners:

| Area | Owner |
| --- | --- |
| Catalog operations (review queue, source registration, freshness) | *unassigned - assign before external rollout* |
| Service operations (deployments, backups, incidents) | *unassigned - assign before external rollout* |

## Failed crawls

1. `GET /v1/admin/crawl-jobs/{id}` for the job, or query `crawl_jobs` for rows
   in state `failed` ordered by `updated_at`.
2. Read `last_error`. A `destination refused:` prefix means the egress guard
   rejected the target; that is a configuration or source problem, not a
   transient fault, and it must not be worked around by widening the guard.
3. Transient failures retry on their own with bounded backoff. Confirm
   `attempts` is below `max_attempts` and leave it alone.
4. The last published catalog version stays in force throughout. A failed crawl
   never removes or changes published data.
5. If a source is permanently gone, disable it (`sources.enabled = false`) and
   raise a review task for the records that depended on it.

## A bad catalog publication

1. Identify the revision: `GET /v1/catalog/items/{id}/history`.
2. Prepare a corrected draft, submit it for review and have a *different*
   reviewer publish it. Publication supersedes the previous revision
   atomically; the bad revision is retained, not deleted.
3. Do not delete the bad revision. Saved recommendations reference it, and the
   database refuses the delete for exactly that reason.
4. Recommendations already saved are immutable and keep showing what was known
   at the time. Affected users re-run their scenario to get a new result.
5. Check `audit_events` for `catalog.published` to confirm who published what.

## Database outage

1. `GET /health/ready` reports `not_ready` while the database is unreachable;
   `/health/live` still reports `live`. A healthy API does not imply a fresh
   catalog, and neither implies a working database.
2. Restore database service first. The API recovers on its own through
   `pool_pre_ping`; no deployment is needed.
3. Crawl jobs that were running when the database went away lose their leases
   and are reclaimed automatically once it returns. Lease fencing prevents a
   stale worker from overwriting the newer attempt.

## Excessive review backlog

1. `GET /v1/admin/freshness/catalog` lists records whose prices or
   specifications are past the freshness policy.
2. Stale critical facts are excluded from confident recommendations already, so
   the backlog degrades coverage rather than correctness.
3. Reduce source count or refresh frequency before increasing them. Measure
   review time per source; manual curation capacity is the real limit on
   catalog expansion.

## Secret rotation

1. Rotate the runtime role's password, then the migration role's, separately.
2. Deploy the new runtime credential and restart the API and worker processes.
   They hold no long-lived state.
3. Session tokens are unaffected; revoke them explicitly by setting
   `sessions.revoked_at` if rotation was prompted by a suspected compromise.

## Restore

1. Restore the most recent base backup into an **isolated** environment, never
   over the live database.
2. Replay WAL to the required point in time. A daily SQL dump alone does not
   meet the one-hour recovery-point target.
3. Verify: row counts on `catalog_revisions` and `recommendation_runs`, and one
   known recommendation returned unchanged by
   `GET /v1/recommendations/{id}`.
4. Record the elapsed time. The four-hour recovery-time target is a claim that
   has to be demonstrated in a timed rehearsal before it is advertised.

## Rollback

1. Schema changes are additive by preference, so the previous application
   release remains usable against the current schema.
2. Roll the application back first and confirm `/health/ready`.
3. Roll a migration back only if the previous release genuinely cannot run
   against the current schema, and only after checking that the down path was
   exercised in staging. `alembic downgrade` is reviewed code, not a reflex.
