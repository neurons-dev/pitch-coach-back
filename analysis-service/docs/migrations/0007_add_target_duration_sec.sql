\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS target_duration_sec INTEGER;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_jobs_target_duration_sec_check'
    ) THEN
        ALTER TABLE analysis_jobs
            ADD CONSTRAINT analysis_jobs_target_duration_sec_check
            CHECK (
                target_duration_sec IS NULL
                OR target_duration_sec > 0
            );
    END IF;
END $$;

COMMIT;
