-- Radiological images, stored the same way lab reports are: the file lives on
-- disk and only a relative path is kept here, so the upload directory can move
-- without rewriting rows.
--
-- Separate from lab_report rather than a column on it: an image has no
-- severity, is never analysed by the lab pipeline, and carries fields
-- (modality, body part) that would be null on every report row.
CREATE TABLE IF NOT EXISTS radiology_image (
    id          UUID PRIMARY KEY,

    patient_id  UUID         NOT NULL REFERENCES patient (id) ON DELETE CASCADE,

    -- Path relative to the configured upload directory, never absolute.
    image_path  VARCHAR(500) NOT NULL,

    -- Mirrors the Modality enum, persisted with @Enumerated(EnumType.STRING).
    modality    VARCHAR(16)  NOT NULL CHECK (modality IN
                    ('XRAY', 'CT', 'MRI', 'ULTRASOUND', 'PET', 'MAMMOGRAPHY', 'OTHER')),

    -- "Chest", "Left knee". Free text: the useful vocabulary here is long and
    -- a constraint would reject legitimate entries.
    body_part   VARCHAR(80),

    description VARCHAR(500),

    created_at  TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- The only query on this table is "this patient's images, newest first", so
-- the sort column is part of the index rather than a separate sort step.
CREATE INDEX IF NOT EXISTS idx_radiology_image_patient
    ON radiology_image (patient_id, created_at DESC);
