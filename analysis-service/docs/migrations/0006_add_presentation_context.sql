\set ON_ERROR_STOP on

BEGIN;

ALTER TABLE analysis_jobs
    ADD COLUMN IF NOT EXISTS presentation_title VARCHAR(100),
    ADD COLUMN IF NOT EXISTS practice_type_code VARCHAR;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_jobs_presentation_title_check'
    ) THEN
        ALTER TABLE analysis_jobs
            ADD CONSTRAINT analysis_jobs_presentation_title_check
            CHECK (
                presentation_title IS NULL
                OR char_length(trim(presentation_title)) > 0
            );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'analysis_jobs_practice_type_code_check'
    ) THEN
        ALTER TABLE analysis_jobs
            ADD CONSTRAINT analysis_jobs_practice_type_code_check
            CHECK (
                practice_type_code IS NULL
                OR char_length(trim(practice_type_code)) > 0
            );
    END IF;

END $$;

COMMIT;
