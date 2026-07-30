\set ON_ERROR_STOP on

-- This migration is intentionally non-transactional.
-- Run it directly with psql. CREATE INDEX CONCURRENTLY cannot run inside a
-- transaction block.

SELECT COALESCE(
    (
        SELECT NOT (indisvalid AND indisready)
        FROM pg_index
        WHERE indexrelid = to_regclass('idx_analysis_jobs_claim')
    ),
    false
) AS claim_index_invalid \gset

\if :claim_index_invalid
    \echo 'Dropping invalid idx_analysis_jobs_claim before retry'
    DROP INDEX CONCURRENTLY idx_analysis_jobs_claim;
\endif

SELECT COALESCE(
    (
        SELECT NOT (indisvalid AND indisready)
        FROM pg_index
        WHERE indexrelid = to_regclass('idx_analysis_jobs_expired_lease')
    ),
    false
) AS expired_lease_index_invalid \gset

\if :expired_lease_index_invalid
    \echo 'Dropping invalid idx_analysis_jobs_expired_lease before retry'
    DROP INDEX CONCURRENTLY idx_analysis_jobs_expired_lease;
\endif

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_jobs_claim
    ON analysis_jobs (created_at, id)
    WHERE status = 'queued';

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_jobs_expired_lease
    ON analysis_jobs (lease_expires_at, id)
    WHERE status = 'processing';

SELECT (
    count(*) = 2
    AND bool_and(indisvalid AND indisready)
) AS new_indexes_valid
FROM pg_index
WHERE indexrelid IN (
    to_regclass('idx_analysis_jobs_claim'),
    to_regclass('idx_analysis_jobs_expired_lease')
)
\gset

\if :new_indexes_valid
    \echo 'New Job Queue indexes are valid'
\else
    \echo 'New Job Queue indexes are not valid; legacy indexes were kept'
    \quit 3
\endif
