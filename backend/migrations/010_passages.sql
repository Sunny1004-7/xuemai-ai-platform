CREATE TABLE ai_resource_passages (
 id INTEGER PRIMARY KEY,
 resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
 version INTEGER NOT NULL,
 locator TEXT NOT NULL,
 ordinal INTEGER NOT NULL,
 content TEXT NOT NULL
);
CREATE INDEX passage_resource ON ai_resource_passages(resource_id,version);
INSERT OR IGNORE INTO resource_index_queue SELECT id FROM resources;
