-- 旧资源级FTS行号与新段落主键可能重合，统一重建派生索引。
-- 资源正文、版本、会话引用快照及所有学习记录均保留。
DELETE FROM ai_resource_fts;
DELETE FROM ai_resource_passages;
INSERT OR IGNORE INTO resource_index_queue SELECT id FROM resources;
