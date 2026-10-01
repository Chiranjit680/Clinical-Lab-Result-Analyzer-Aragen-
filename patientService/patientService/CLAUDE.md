We are building a patient record keeping service for a clinical lab analyzer 

the db schema looks like this 
CREATE TABLE patient (
    id               UUID PRIMARY KEY,
    full_name        VARCHAR(120) NOT NULL,
    date_of_birth    DATE NOT NULL,
    sex              VARCHAR(10) NOT NULL,
    blood_group      VARCHAR(5),
    pregnant         BOOLEAN NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE lab_report (
    id           UUID PRIMARY KEY,
    patient_id   UUID NOT NULL REFERENCES patient(id) ON DELETE CASCADE,
    report_path  VARCHAR(500) NOT NULL,
    status       VARCHAR(10) NOT NULL
                 CHECK (status IN ('NORMAL', 'WARNING', 'CRITICAL')),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_lab_report_patient ON lab_report (patient_id);

we are writing this service in springboot
