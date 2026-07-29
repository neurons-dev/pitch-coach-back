\set ON_ERROR_STOP on

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS lease_token UUID;
