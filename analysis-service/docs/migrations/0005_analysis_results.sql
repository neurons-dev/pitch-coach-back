\set ON_ERROR_STOP on

-- Creates analysis_results / analysis_metric_scores / feedback_items if they don't
-- already exist, then adds the version-tracking columns needed for #15 regardless of
-- whether the tables were just created here or already existed beforehand.

BEGIN;

CREATE TABLE IF NOT EXISTS analysis_results (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id                UUID NOT NULL UNIQUE
                              REFERENCES analysis_jobs(id) ON DELETE CASCADE,
    overall_score         SMALLINT NOT NULL
                              CHECK (overall_score BETWEEN 0 AND 100),
    coach_comment         TEXT,
    transcript_text       TEXT,
    transcript_segments   JSONB NOT NULL DEFAULT '[]'::jsonb,
    total_speech_ms       BIGINT CHECK (total_speech_ms IS NULL OR total_speech_ms >= 0),
    total_silence_ms      BIGINT CHECK (total_silence_ms IS NULL OR total_silence_ms >= 0),
    model_info            JSONB NOT NULL DEFAULT '{}'::jsonb,
    analyzed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis_metric_scores (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_result_id    UUID NOT NULL
                              REFERENCES analysis_results(id) ON DELETE CASCADE,
    metric_code           VARCHAR NOT NULL
                              CHECK (metric_code IN (
                                  'SPEED', 'FILLER', 'PRONUNCIATION',
                                  'DELIVERY', 'STRUCTURE', 'FLUENCY'
                              )),
    score                 SMALLINT NOT NULL CHECK (score BETWEEN 0 AND 100),
    raw_value             NUMERIC(12, 3),
    unit                  VARCHAR,
    details               JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (analysis_result_id, metric_code)
);

CREATE TABLE IF NOT EXISTS feedback_items (
    id                    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    analysis_result_id    UUID NOT NULL
                              REFERENCES analysis_results(id) ON DELETE CASCADE,
    metric_code           VARCHAR
                              CHECK (metric_code IS NULL OR metric_code IN (
                                  'SPEED', 'FILLER', 'PRONUNCIATION',
                                  'DELIVERY', 'STRUCTURE', 'FLUENCY'
                              )),
    item_type             VARCHAR NOT NULL
                              CHECK (item_type IN ('summary', 'strength', 'improvement')),
    title                 VARCHAR NOT NULL CHECK (char_length(trim(title)) > 0),
    description           TEXT NOT NULL,
    evidence              JSONB NOT NULL DEFAULT '{}'::jsonb,
    sort_order            SMALLINT NOT NULL DEFAULT 0,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_results_analyzed
    ON analysis_results (analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_metric_scores_code_result
    ON analysis_metric_scores (metric_code, analysis_result_id);

CREATE INDEX IF NOT EXISTS idx_feedback_result_order
    ON feedback_items (analysis_result_id, sort_order);

-- Version columns (#15): record the pipeline/STT/scoring versions that actually
-- produced the result, independent of analysis_jobs.analysis_version (the version
-- requested at job-creation time). Safe as NOT NULL with no default because both a
-- freshly-created table and the pre-existing empty table have zero rows.
ALTER TABLE analysis_results
    ADD COLUMN IF NOT EXISTS pipeline_version VARCHAR NOT NULL;
ALTER TABLE analysis_results
    ADD COLUMN IF NOT EXISTS stt_model_version VARCHAR NOT NULL;
ALTER TABLE analysis_results
    ADD COLUMN IF NOT EXISTS scoring_rule_version VARCHAR NOT NULL;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'analysis_results_pipeline_version_check'
    ) THEN
        ALTER TABLE analysis_results
            ADD CONSTRAINT analysis_results_pipeline_version_check
            CHECK (char_length(trim(pipeline_version)) > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'analysis_results_stt_model_version_check'
    ) THEN
        ALTER TABLE analysis_results
            ADD CONSTRAINT analysis_results_stt_model_version_check
            CHECK (char_length(trim(stt_model_version)) > 0);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'analysis_results_scoring_rule_version_check'
    ) THEN
        ALTER TABLE analysis_results
            ADD CONSTRAINT analysis_results_scoring_rule_version_check
            CHECK (char_length(trim(scoring_rule_version)) > 0);
    END IF;
END $$;

COMMIT;
