-- =============================================================================
-- EventFlow AI — PostgreSQL Schema (with PostGIS)
-- =============================================================================
--
-- Run this against a real PostgreSQL 14+ instance with PostGIS installed:
--   psql -U <user> -d <database> -f 001_initial_schema.sql
--
-- IMPORTANT, stated honestly: this schema has NOT been executed against a
-- real PostgreSQL server during development (the build sandbox has no
-- database server and no network access to install one). It is written to
-- standard, documented PostgreSQL 14+ / PostGIS 3+ syntax and reviewed
-- carefully for correctness, but you are the first to actually run it.
-- Please run this migration against your real instance and report any
-- error before relying on it for a live demo.
--
-- Design note on real vs. user-entered data:
-- `corridors` is seeded from the REAL ASTRAM Bengaluru dataset (22 real
-- corridors with real centroid coordinates and real historical incident
-- counts) via migration 002. `events` is where NEW events entered through
-- the EventFlow AI portal are stored — these are real user-entered rows
-- once the app is in use, distinct from the historical ASTRAM training data
-- that the ML models in ml_pipeline/ were trained on.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- users — auth + role-based access control
-- =============================================================================
CREATE TYPE user_role AS ENUM ('admin', 'traffic_officer', 'public_user');

CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name       VARCHAR(255) NOT NULL,
    role            user_role NOT NULL DEFAULT 'public_user',
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- =============================================================================
-- corridors — REAL corridor reference data (seeded from the real ASTRAM
-- dataset via migration 002; this is the geographic backbone every event,
-- prediction, and route in this system is anchored to)
-- =============================================================================
CREATE TABLE corridors (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    corridor_name           VARCHAR(255) UNIQUE NOT NULL,
    centroid_location       GEOGRAPHY(POINT, 4326) NOT NULL,
    historical_incident_count INTEGER NOT NULL DEFAULT 0,
    zone                    VARCHAR(255),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_corridors_location ON corridors USING GIST(centroid_location);
CREATE INDEX idx_corridors_name ON corridors(corridor_name);

-- =============================================================================
-- locations — specific point locations tied to events (distinct from
-- corridors, since an event has a specific lat/lon, not just "a corridor")
-- =============================================================================
CREATE TABLE locations (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    point           GEOGRAPHY(POINT, 4326) NOT NULL,
    address         TEXT,
    nearest_corridor_id UUID REFERENCES corridors(id) ON DELETE SET NULL,
    distance_to_corridor_km NUMERIC(6, 3),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_locations_point ON locations USING GIST(point);

-- =============================================================================
-- events — events entered through the EventFlow AI portal (planned or
-- unplanned), the central table the rest of the app revolves around
-- =============================================================================
CREATE TYPE event_category AS ENUM (
    'political_rally', 'festival', 'sports_event',
    'construction', 'accident', 'emergency_gathering'
);
CREATE TYPE crowd_size_level AS ENUM ('low', 'medium', 'high', 'extreme');
CREATE TYPE event_status AS ENUM ('upcoming', 'active', 'completed', 'cancelled');

CREATE TABLE events (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_name          VARCHAR(255) NOT NULL,
    category            event_category NOT NULL,
    location_id         UUID NOT NULL REFERENCES locations(id) ON DELETE RESTRICT,
    expected_crowd_size  crowd_size_level NOT NULL,
    weather_condition    VARCHAR(100),
    start_datetime       TIMESTAMPTZ NOT NULL,
    end_datetime         TIMESTAMPTZ NOT NULL,
    affected_roads        TEXT[],
    status                event_status NOT NULL DEFAULT 'upcoming',
    created_by_id          UUID NOT NULL REFERENCES users(id) ON DELETE SET NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_event_times CHECK (end_datetime > start_datetime)
);

CREATE INDEX idx_events_status ON events(status);
CREATE INDEX idx_events_start ON events(start_datetime);
CREATE INDEX idx_events_category ON events(category);
CREATE INDEX idx_events_created_by ON events(created_by_id);

-- =============================================================================
-- traffic_history — real historical incident records (seeded from the real
-- ASTRAM dataset via migration 002: ~8,054 real cleaned incident rows)
-- =============================================================================
CREATE TABLE traffic_history (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    corridor_id          UUID REFERENCES corridors(id) ON DELETE SET NULL,
    event_cause           VARCHAR(100) NOT NULL,
    occurred_at            TIMESTAMPTZ NOT NULL,
    duration_minutes        NUMERIC(10, 2),
    required_road_closure    BOOLEAN NOT NULL DEFAULT FALSE,
    priority                  VARCHAR(20),
    source                     VARCHAR(50) NOT NULL DEFAULT 'astram_real_dataset',
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_traffic_history_corridor ON traffic_history(corridor_id);
CREATE INDEX idx_traffic_history_occurred ON traffic_history(occurred_at);
CREATE INDEX idx_traffic_history_cause ON traffic_history(event_cause);

-- =============================================================================
-- predictions — every AI prediction made for an event, with full audit trail
-- (input features actually used, confidence, explanation) so post-event
-- learning can compare predicted vs actual
-- =============================================================================
CREATE TYPE traffic_level AS ENUM ('low', 'medium', 'high', 'critical');

CREATE TABLE predictions (
    id                      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id                UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    congestion_score         NUMERIC(5, 2) NOT NULL CHECK (congestion_score >= 0 AND congestion_score <= 100),
    traffic_level             traffic_level NOT NULL,
    predicted_duration_minutes NUMERIC(10, 2) NOT NULL,
    predicted_delay_minutes    NUMERIC(10, 2) NOT NULL,
    affected_radius_km          NUMERIC(6, 2) NOT NULL,
    severity_score                NUMERIC(4, 3) NOT NULL CHECK (severity_score >= 0 AND severity_score <= 1),
    confidence_score               NUMERIC(4, 3) NOT NULL CHECK (confidence_score >= 0 AND confidence_score <= 1),
    model_r2_duration                 NUMERIC(5, 4),
    model_r2_severity                  NUMERIC(5, 4),
    rare_category_low_confidence        BOOLEAN NOT NULL DEFAULT FALSE,
    explanation                          TEXT NOT NULL,
    input_features_used                   JSONB NOT NULL,
    data_provenance                         VARCHAR(50) NOT NULL DEFAULT 'real_historical_astram_event_log',
    created_at                                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_predictions_event ON predictions(event_id);

-- =============================================================================
-- resources — resource recommendation per event (manpower, barricading)
-- =============================================================================
CREATE TABLE resources (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id                    UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    prediction_id                 UUID REFERENCES predictions(id) ON DELETE SET NULL,
    recommended_officer_count       INTEGER NOT NULL CHECK (recommended_officer_count >= 0),
    recommended_ambulance_count       INTEGER NOT NULL DEFAULT 0,
    recommended_control_room_count      INTEGER NOT NULL DEFAULT 0,
    barricade_point_count                 INTEGER NOT NULL DEFAULT 0,
    barricade_spacing_km                    NUMERIC(6, 3),
    estimated_footprint_km                    NUMERIC(6, 3),
    historical_road_closure_rate                NUMERIC(4, 3),
    rationale                                     TEXT NOT NULL,
    actual_officer_count_deployed                   INTEGER,
    created_at                                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                                          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_resources_event ON resources(event_id);

-- =============================================================================
-- diversion_routes — recommended alternate corridors per event
-- =============================================================================
CREATE TABLE diversion_routes (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id             UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    alternate_corridor_id  UUID NOT NULL REFERENCES corridors(id) ON DELETE CASCADE,
    distance_km             NUMERIC(6, 3) NOT NULL,
    historical_total_incidents INTEGER NOT NULL DEFAULT 0,
    estimated_delay_minutes      NUMERIC(8, 2),
    route_rank                    INTEGER NOT NULL DEFAULT 1,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_diversion_routes_event ON diversion_routes(event_id);

-- =============================================================================
-- post_event_feedback — real vs predicted, for the post-event learning loop
-- =============================================================================
CREATE TABLE post_event_feedback (
    id                          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id                    UUID NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    prediction_id                 UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    actual_duration_minutes          NUMERIC(10, 2),
    actual_delay_minutes               NUMERIC(10, 2),
    actual_officer_count_used            INTEGER,
    actual_congestion_score                NUMERIC(5, 2),
    duration_prediction_error_minutes        NUMERIC(10, 2),
    delay_prediction_error_minutes             NUMERIC(10, 2),
    submitted_by_id                              UUID REFERENCES users(id) ON DELETE SET NULL,
    notes                                          TEXT,
    created_at                                       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_post_event_feedback_event ON post_event_feedback(event_id);

-- =============================================================================
-- public_advisories — generated citizen-facing messages per event
-- =============================================================================
CREATE TABLE public_advisories (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    sms_text         TEXT NOT NULL,
    notification_text TEXT NOT NULL,
    display_board_text TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_public_advisories_event ON public_advisories(event_id);

-- =============================================================================
-- Trigger: auto-update updated_at columns
-- =============================================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_events_updated_at BEFORE UPDATE ON events
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_resources_updated_at BEFORE UPDATE ON resources
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
