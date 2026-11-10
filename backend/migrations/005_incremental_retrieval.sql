CREATE VIRTUAL TABLE IF NOT EXISTS ai_resource_fts USING fts5(
 resource_id UNINDEXED, course_id UNINDEXED, title UNINDEXED, excerpt UNINDEXED, tokens);
CREATE TABLE resource_index_queue(resource_id INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO resource_index_queue SELECT id FROM resources;
CREATE TRIGGER resource_index_insert AFTER INSERT ON resources BEGIN
 INSERT OR IGNORE INTO resource_index_queue VALUES(NEW.id);
END;
CREATE TRIGGER resource_index_update AFTER UPDATE ON resources BEGIN
 INSERT OR IGNORE INTO resource_index_queue VALUES(NEW.id);
END;
CREATE TRIGGER resource_index_delete AFTER DELETE ON resources BEGIN
 INSERT OR IGNORE INTO resource_index_queue VALUES(OLD.id);
END;
