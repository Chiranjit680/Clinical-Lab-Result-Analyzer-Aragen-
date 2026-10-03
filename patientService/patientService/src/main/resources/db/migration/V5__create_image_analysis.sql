-- One VLM analysis per radiological image.
--
-- image_id is UNIQUE for the same reason report_id is on the analysis table:
-- re-analysing an image replaces its result rather than accumulating, and the
-- constraint makes that the database's rule instead of a convention the service
-- has to remember.
--
-- The scannable fields are real columns; the agents' full response is kept in
-- JSONB so the whole-image summary and every per-tile report can be re-rendered
-- without a migration each time that response shape changes.
CREATE TABLE IF NOT EXISTS image_analysis (
    id             UUID PRIMARY KEY,

    image_id       UUID        NOT NULL UNIQUE REFERENCES radiology_image (id) ON DELETE CASCADE,

    -- The question the agents were asked. Defaulted by the agent service when
    -- the caller does not supply one, so it is worth recording which one ran.
    question       VARCHAR(2000),

    -- The aggregator's merged answer: the one piece of text a reader wants.
    answer         TEXT        NOT NULL,

    -- Which model produced it. Runs are not comparable across models, and this
    -- is configurable per deployment.
    model          VARCHAR(120),

    -- Correlates this row with the agent service's own log of the run.
    run_id         VARCHAR(64),

    -- How many tile agents reported. Derived from the grid, which is tunable.
    tile_count     INTEGER     NOT NULL DEFAULT 0,

    -- An image analysis is minutes of work, so the duration is worth recording
    -- rather than reconstructing from logs later.
    duration_ms    INTEGER,

    payload        JSONB       NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
