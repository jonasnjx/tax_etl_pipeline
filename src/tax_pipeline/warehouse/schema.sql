-- warehouse schema: dimensions, fact, dq metrics, corrections audit.
-- surrogate keys come from sequences (only dim_taxpayer needs one, for scd2 versions).

CREATE SEQUENCE IF NOT EXISTS seq_taxpayer_sk START 1;
CREATE SEQUENCE IF NOT EXISTS seq_correction_id START 1;

-- taxpayer dimension with scd2 history (multiple versions per taxpayer_id)
CREATE TABLE IF NOT EXISTS dim_taxpayer (
    taxpayer_sk           BIGINT PRIMARY KEY,
    taxpayer_id           VARCHAR,
    nric                  VARCHAR,
    full_name             VARCHAR,
    filing_status         VARCHAR,
    occupation            VARCHAR,
    residential_status    VARCHAR,
    postal_code           VARCHAR,
    housing_type          VARCHAR,
    number_of_dependents  VARCHAR,
    valid_from            DATE,
    valid_to              DATE,
    is_current            BOOLEAN
);

-- employer reference data (one row per employer; no history needed)
CREATE TABLE IF NOT EXISTS dim_employer (
    employer_id     VARCHAR PRIMARY KEY,
    company_name    VARCHAR,
    uen             VARCHAR,
    industry        VARCHAR,
    address         VARCHAR,
    employee_count  INTEGER
);

-- one row per actual return (taxpayer x assessment year)
CREATE TABLE IF NOT EXISTS fact_tax_returns (
    taxpayer_id            VARCHAR,
    assessment_year        INTEGER,
    taxpayer_sk            BIGINT,
    employer_id            VARCHAR,
    filing_date            DATE,
    batch_date             DATE,
    record_type            VARCHAR,
    annual_income_sgd      DOUBLE,
    chargeable_income_sgd  DOUBLE,
    tax_payable_sgd        DOUBLE,
    tax_paid_sgd           DOUBLE,
    total_reliefs_sgd      DOUBLE,
    cpf_contributions_sgd  DOUBLE,
    foreign_income_sgd     DOUBLE,
    is_corrected           BOOLEAN,
    PRIMARY KEY (taxpayer_id, assessment_year)
);

-- dq scores per domain, tracked per batch over time
CREATE TABLE IF NOT EXISTS agg_data_quality_metrics (
    batch          VARCHAR,
    domain         VARCHAR,
    score          DOUBLE,
    passing_count  INTEGER,
    total_count    INTEGER,
    computed_at    TIMESTAMP,
    PRIMARY KEY (batch, domain)
);

-- audit trail: the old values that a correction overwrote
CREATE TABLE IF NOT EXISTS fact_corrections (
    correction_id              BIGINT PRIMARY KEY,
    taxpayer_id                VARCHAR,
    assessment_year            INTEGER,
    corrected_at               DATE,
    old_annual_income_sgd      DOUBLE,
    old_chargeable_income_sgd  DOUBLE,
    old_tax_payable_sgd        DOUBLE,
    old_tax_paid_sgd           DOUBLE,
    old_total_reliefs_sgd      DOUBLE
);
