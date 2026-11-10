CREATE TABLE teaching_runs(
 id INTEGER PRIMARY KEY, conversation_id INTEGER NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id), course_id INTEGER NOT NULL REFERENCES courses(id),
 knowledge_id INTEGER REFERENCES knowledge_points(id) ON DELETE SET NULL,
 check_id INTEGER REFERENCES tutoring_checks(id) ON DELETE SET NULL,
 state TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'planned',
 created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_attempts_time_skill ON attempts(student_id,created_at,question_id);
CREATE INDEX idx_mastery_knowledge ON mastery(knowledge_id,student_id);
CREATE INDEX idx_teaching_runs_conversation ON teaching_runs(user_id,conversation_id,id);
