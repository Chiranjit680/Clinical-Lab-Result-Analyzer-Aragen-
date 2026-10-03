-- One analysis per report.
--
-- report_id is UNIQUE on purpose: re-analysing a report replaces its result
-- rather than adding another, and the constraint makes that the database's
-- rule instead of a convention the service has to remember. A report never
-- ends up with two "current" analyses, whatever the application does.
--
-- The severity counts are real columns because they are what gets filtered and
-- displayed; the full analyzer response is kept in JSONB so explanations,
-- sources and next steps can be re-rendered without a migration every time
-- that response shape changes.
CREATE TABLE IF NOT EXISTS analysis (
    id             UUID PRIMARY KEY,

    report_id      UUID        NOT NULL UNIQUE REFERENCES lab_report (id) ON DELETE CASCADE,

    -- LangGraph checkpoint id, so a stored analysis can still be resumed for
    -- follow-up chat. Goes stale when the analyzer restarts, since threads are
    -- held in process memory.
    thread_id      VARCHAR(64),

    -- Worst finding in the run, mirroring ReportStatus.
    status         VARCHAR(10) NOT NULL CHECK (status IN ('NORMAL', 'WARNING', 'CRITICAL')),

    critical_count INTEGER     NOT NULL DEFAULT 0,
    warning_count  INTEGER     NOT NULL DEFAULT 0,
    normal_count   INTEGER     NOT NULL DEFAULT 0,
    unknown_count  INTEGER     NOT NULL DEFAULT 0,
    error_count    INTEGER     NOT NULL DEFAULT 0,

    -- Analyses are slow and variable, so the duration is worth recording
    -- rather than reconstructing from logs later.
    duration_ms    INTEGER,

    payload        JSONB       NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
