\set ON_ERROR_STOP on

CREATE TABLE IF NOT EXISTS analysis_jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    idempotency_key     VARCHAR NOT NULL UNIQUE,
    session_id          UUID NOT NULL,
    user_id             BIGINT NOT NULL,

    audio_object_key    VARCHAR NOT NULL,
    audio_content_type  VARCHAR,
    audio_size_bytes    BIGINT CHECK (audio_size_bytes IS NULL OR audio_size_bytes >= 0),
    duration_ms         BIGINT CHECK (duration_ms IS NULL OR duration_ms >= 0),

    analysis_version    VARCHAR NOT NULL DEFAULT 'v1',
    status              VARCHAR NOT NULL DEFAULT 'queued'
                            CHECK (status IN ('queued', 'processing', 'completed', 'failed', 'cancelled')),
    current_stage       VARCHAR,
    progress_percent    SMALLINT NOT NULL DEFAULT 0 CHECK (progress_percent BETWEEN 0 AND 100),

    retry_count         SMALLINT NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries         SMALLINT NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    error_code          VARCHAR,
    error_message       TEXT,

    lease_expires_at    TIMESTAMPTZ,

    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_session_created
    ON analysis_jobs (session_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_user_created
    ON analysis_jobs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_pending
    ON analysis_jobs (status, created_at)
    WHERE status IN ('queued', 'processing');

CREATE INDEX IF NOT EXISTS idx_analysis_jobs_lease
    ON analysis_jobs (lease_expires_at)
    WHERE status = 'processing';

CREATE UNIQUE INDEX IF NOT EXISTS uq_analysis_jobs_active_session
    ON analysis_jobs (session_id)
    WHERE status IN ('queued', 'processing');
