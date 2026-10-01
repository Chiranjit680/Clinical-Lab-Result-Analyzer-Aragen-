-- Patients. Mapped by the Identity entity, which is annotated @Table(name = "patient").
--
-- IF NOT EXISTS because this schema was originally created by hand: the
-- migration has to be a no-op against those databases while still building a
-- fresh one from nothing.
CREATE TABLE IF NOT EXISTS patient (
    id            UUID PRIMARY KEY,
    full_name     VARCHAR(120) NOT NULL,
    date_of_birth DATE         NOT NULL,
    sex           VARCHAR(10)  NOT NULL,
    blood_group   VARCHAR(5),
    pregnant      BOOLEAN      NOT NULL DEFAULT FALSE,
    -- IdentityService sets both in code; the defaults are a safety net for
    -- rows inserted outside the application.
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT now()
);
