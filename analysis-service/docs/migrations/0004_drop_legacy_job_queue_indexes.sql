\set ON_ERROR_STOP on

-- This migration is intentionally non-transactional.
-- It is separated from index creation so legacy indexes remain available until
-- both replacement indexes are confirmed valid.

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
    DROP INDEX CONCURRENTLY IF EXISTS idx_analysis_jobs_pending;
    DROP INDEX CONCURRENTLY IF EXISTS idx_analysis_jobs_lease;
\else
    \echo 'Replacement indexes are not valid; refusing to drop legacy indexes'
    \quit 3
\endif
