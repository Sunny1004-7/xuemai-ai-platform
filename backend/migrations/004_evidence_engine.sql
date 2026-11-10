ALTER TABLE users ADD COLUMN active INTEGER NOT NULL DEFAULT 1;
ALTER TABLE mastery ADD COLUMN alpha REAL;
ALTER TABLE mastery ADD COLUMN beta REAL;
ALTER TABLE mastery ADD COLUMN effective_count REAL NOT NULL DEFAULT 0;
ALTER TABLE knowledge_points ADD COLUMN difficulty INTEGER NOT NULL DEFAULT 1;
ALTER TABLE questions ADD COLUMN skill TEXT NOT NULL DEFAULT 'concept';
ALTER TABLE questions ADD COLUMN diagnostic_map TEXT NOT NULL DEFAULT '{}';
CREATE TABLE evidence_updates(
    id INTEGER PRIMARY KEY,
    attempt_id INTEGER NOT NULL UNIQUE REFERENCES attempts(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id),
    knowledge_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    before_value REAL NOT NULL,
    after_value REAL NOT NULL,
    weight REAL NOT NULL,
    quality REAL NOT NULL,
    details TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE review_schedule(
    student_id INTEGER NOT NULL REFERENCES users(id),
    question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
    interval_days REAL NOT NULL DEFAULT 1,
    ease REAL NOT NULL DEFAULT 2.5,
    repetitions INTEGER NOT NULL DEFAULT 0,
    last_quality INTEGER,
    next_due TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY(student_id,question_id)
);
CREATE TABLE assignment_baselines(
    assignment_id INTEGER NOT NULL REFERENCES assignments(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES users(id),
    knowledge_id INTEGER NOT NULL REFERENCES knowledge_points(id) ON DELETE CASCADE,
    value REAL NOT NULL,
    evidence_count REAL NOT NULL,
    PRIMARY KEY(assignment_id,student_id,knowledge_id)
);
CREATE TABLE content_revisions(version INTEGER PRIMARY KEY, applied_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE INDEX idx_evidence_student_knowledge ON evidence_updates(student_id,knowledge_id);
UPDATE users SET active=0 WHERE username='student2' AND synthetic=1;
DELETE FROM sessions WHERE user_id IN (SELECT id FROM users WHERE active=0);
DELETE FROM class_members WHERE student_id IN (SELECT id FROM users WHERE active=0);
