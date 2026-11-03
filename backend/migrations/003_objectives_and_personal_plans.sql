ALTER TABLE chapters ADD COLUMN objectives TEXT NOT NULL DEFAULT '[]';
ALTER TABLE knowledge_points ADD COLUMN objectives TEXT NOT NULL DEFAULT '[]';
CREATE TABLE learning_goals(
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    target_date TEXT,
    daily_minutes INTEGER NOT NULL DEFAULT 25,
    knowledge_ids TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','completed','paused')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE study_plans(
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id INTEGER NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    goal_id INTEGER REFERENCES learning_goals(id) ON DELETE SET NULL,
    knowledge_id INTEGER REFERENCES knowledge_points(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    kind TEXT NOT NULL DEFAULT 'practice' CHECK(kind IN ('practice','video','review','experiment','reading')),
    scheduled_date TEXT,
    estimated_minutes INTEGER NOT NULL DEFAULT 15,
    status TEXT NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','completed','skipped')),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_goals_student_course ON learning_goals(student_id,course_id);
CREATE INDEX idx_plans_student_course ON study_plans(student_id,course_id,status);
