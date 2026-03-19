CREATE TABLE IF NOT EXISTS class_groups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    UNIQUE (classroom_id, name)
);

CREATE TABLE IF NOT EXISTS class_group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    classroom_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (classroom_id) REFERENCES classrooms(id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES class_groups(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (classroom_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_groups_classroom_id ON class_groups (classroom_id);
CREATE INDEX IF NOT EXISTS idx_class_group_members_classroom_id ON class_group_members (classroom_id);
CREATE INDEX IF NOT EXISTS idx_class_group_members_group_id ON class_group_members (group_id);
CREATE INDEX IF NOT EXISTS idx_class_group_members_student_id ON class_group_members (student_id);
