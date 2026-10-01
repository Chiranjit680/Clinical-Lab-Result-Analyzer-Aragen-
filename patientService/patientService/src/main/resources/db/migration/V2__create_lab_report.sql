-- Lab reports, one per uploaded document, owned by a patient.
CREATE TABLE IF NOT EXISTS lab_report (
    id          UUID PRIMARY KEY,
    -- Deleting a patient removes their reports; the stored files are cleaned
    -- up separately, since the database does not own them.
    patient_id  UUID         NOT NULL REFERENCES patient (id) ON DELETE CASCADE,
    -- Path relative to the configured upload directory, never absolute.
    report_path VARCHAR(500) NOT NULL,
    -- Mirrors the ReportStatus enum, persisted with @Enumerated(EnumType.STRING).
    -- The CHECK keeps rows written outside the application honest.
    status      VARCHAR(10)  NOT NULL CHECK (status IN ('NORMAL', 'WARNING', 'CRITICAL')),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Supports findByPatientIdOrderByCreatedAtDesc, the only query on this table.
CREATE INDEX IF NOT EXISTS idx_lab_report_patient ON lab_report (patient_id);
