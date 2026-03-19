CREATE TABLE IF NOT EXISTS classrooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    grade INTEGER NOT NULL,
    invite_code VARCHAR(16) NOT NULL UNIQUE,
    teacher_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS class_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    joined_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (classroom_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_classrooms_teacher_id ON classrooms (teacher_id);
CREATE INDEX IF NOT EXISTS idx_classrooms_invite_code ON classrooms (invite_code);
CREATE INDEX IF NOT EXISTS idx_class_members_classroom_id ON class_members (classroom_id);
CREATE INDEX IF NOT EXISTS idx_class_members_student_id ON class_members (student_id);
