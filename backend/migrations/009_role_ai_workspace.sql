CREATE TABLE IF NOT EXISTS ai_conversations (
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 course_id INTEGER NOT NULL REFERENCES courses(id), title TEXT NOT NULL,
 context TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ai_messages (
 id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
 role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
 citations TEXT NOT NULL DEFAULT '[]', mode TEXT NOT NULL DEFAULT 'mock',
 status TEXT NOT NULL DEFAULT 'complete', teaching TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE ai_messages ADD COLUMN model TEXT NOT NULL DEFAULT 'deepseek-flash';
ALTER TABLE ai_messages ADD COLUMN attachments TEXT NOT NULL DEFAULT '[]';
ALTER TABLE ai_messages ADD COLUMN usage TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_messages ADD COLUMN artifact TEXT NOT NULL DEFAULT '{}';
ALTER TABLE ai_conversations ADD COLUMN purpose TEXT NOT NULL DEFAULT 'student';
UPDATE ai_conversations SET purpose='teacher' WHERE user_id IN (SELECT id FROM users WHERE role='teacher');

CREATE TABLE ai_attachments (
 id TEXT PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 course_id INTEGER NOT NULL REFERENCES courses(id),
 conversation_id INTEGER REFERENCES ai_conversations(id),
 filename TEXT NOT NULL,
 media_type TEXT NOT NULL,
 storage_name TEXT NOT NULL,
 bytes INTEGER NOT NULL,
 sha256 TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'ready',
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 deleted_at TEXT
);
CREATE TABLE ai_attachment_chunks (
 id INTEGER PRIMARY KEY,
 attachment_id TEXT NOT NULL REFERENCES ai_attachments(id) ON DELETE CASCADE,
 locator TEXT NOT NULL,
 content TEXT NOT NULL,
 ordinal INTEGER NOT NULL
);
CREATE INDEX attachment_scope ON ai_attachments(user_id,course_id,conversation_id);
CREATE TABLE ai_teacher_drafts (
 id INTEGER PRIMARY KEY,
 user_id INTEGER NOT NULL REFERENCES users(id),
 course_id INTEGER NOT NULL REFERENCES courses(id),
 conversation_id INTEGER NOT NULL REFERENCES ai_conversations(id),
 kind TEXT NOT NULL,
 content TEXT NOT NULL,
 evidence TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'draft',
 saved_resource_id INTEGER REFERENCES resources(id),
 request_key TEXT NOT NULL UNIQUE,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE knowledge_activities (
 knowledge_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
 mode TEXT NOT NULL,
 PRIMARY KEY(knowledge_id,mode)
);
