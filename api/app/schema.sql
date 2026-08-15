-- Vista-UI SQLite schema. Applied idempotently on startup.

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- Persisted event log. The panel keeps no history, so every transition lands here.
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT    NOT NULL,            -- ISO-8601 UTC
    event_type TEXT    NOT NULL,            -- zone_open, zone_restore, arm_away, disarm, alarm, trouble, ...
    partition  INTEGER,
    zone       INTEGER,
    user_num   INTEGER,
    status     TEXT,                        -- open|closed|armed|disarmed|...
    severity   TEXT    NOT NULL DEFAULT 'info',  -- info|warning|alarm
    detail     TEXT,                        -- human text
    raw        TEXT                         -- raw TPI payload
);

CREATE INDEX IF NOT EXISTS idx_events_ts       ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_type     ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_zone     ON events(zone);
CREATE INDEX IF NOT EXISTS idx_events_severity ON events(severity);

-- User-configured zone identity (protocol only reports numbers).
CREATE TABLE IF NOT EXISTS zones (
    number     INTEGER PRIMARY KEY,
    name       TEXT,
    zone_type  TEXT,                        -- door|window|motion|glassbreak|smoke|co|contact|generic
    icon       TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Web Push subscriptions (must survive restarts).
CREATE TABLE IF NOT EXISTS push_subscriptions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    endpoint   TEXT UNIQUE NOT NULL,
    p256dh     TEXT NOT NULL,
    auth       TEXT NOT NULL,
    ua         TEXT,
    created_at TEXT NOT NULL
);
