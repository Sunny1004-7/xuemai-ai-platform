ALTER TABLE study_plans ADD COLUMN target TEXT NOT NULL DEFAULT '{}';
ALTER TABLE study_plans ADD COLUMN completion_event_id INTEGER REFERENCES learning_events(id) ON DELETE SET NULL;
CREATE TABLE sample_entities(
 sample_key TEXT PRIMARY KEY, entity_table TEXT NOT NULL, entity_id INTEGER NOT NULL,
 content_version INTEGER NOT NULL, source TEXT NOT NULL DEFAULT '本地编写教学样例', imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE sample_packages(version INTEGER PRIMARY KEY, seed INTEGER NOT NULL, time_base TEXT NOT NULL, imported_at TEXT DEFAULT CURRENT_TIMESTAMP);
