-- assignments
ALTER TABLE assignments ADD COLUMN topic VARCHAR(255);
ALTER TABLE assignments ADD COLUMN description TEXT;
ALTER TABLE assignments ADD COLUMN school_stage VARCHAR(50);
ALTER TABLE assignments ADD COLUMN grade INTEGER;
ALTER TABLE assignments ADD COLUMN main_subject_id INTEGER;
ALTER TABLE assignments ADD COLUMN related_subject_ids JSON;
ALTER TABLE assignments ADD COLUMN assignment_type VARCHAR(50);
ALTER TABLE assignments ADD COLUMN practical_subtype VARCHAR(50);
ALTER TABLE assignments ADD COLUMN inquiry_subtype VARCHAR(50);
ALTER TABLE assignments ADD COLUMN inquiry_depth VARCHAR(50);
ALTER TABLE assignments ADD COLUMN submission_mode VARCHAR(50);
ALTER TABLE assignments ADD COLUMN duration_weeks INTEGER;
ALTER TABLE assignments ADD COLUMN deadline DATETIME;
ALTER TABLE assignments ADD COLUMN objectives_json JSON;
ALTER TABLE assignments ADD COLUMN phases_json JSON;
ALTER TABLE assignments ADD COLUMN rubric_json JSON;
ALTER TABLE assignments ADD COLUMN created_by INTEGER;
ALTER TABLE assignments ADD COLUMN document_id INTEGER;
ALTER TABLE assignments ADD COLUMN created_at DATETIME;
ALTER TABLE assignments ADD COLUMN updated_at DATETIME;
ALTER TABLE assignments ADD COLUMN is_published BOOLEAN;
ALTER TABLE assignments ADD COLUMN published_at DATETIME;

UPDATE assignments
SET topic = COALESCE(NULLIF(topic, ''), title, '未设置')
WHERE topic IS NULL OR topic = '';

-- submissions
ALTER TABLE submissions ADD COLUMN student_id INTEGER;
ALTER TABLE submissions ADD COLUMN group_id INTEGER;
ALTER TABLE submissions ADD COLUMN phase_index INTEGER;
ALTER TABLE submissions ADD COLUMN step_index INTEGER;
ALTER TABLE submissions ADD COLUMN status VARCHAR(50);
ALTER TABLE submissions ADD COLUMN content_json JSON;
ALTER TABLE submissions ADD COLUMN attachments_json JSON;
ALTER TABLE submissions ADD COLUMN checkpoints_json JSON;
ALTER TABLE submissions ADD COLUMN created_at DATETIME;
ALTER TABLE submissions ADD COLUMN submitted_at DATETIME;
ALTER TABLE submissions ADD COLUMN updated_at DATETIME;

UPDATE submissions SET student_id = COALESCE(student_id, 1);
UPDATE submissions SET phase_index = COALESCE(phase_index, 0);
UPDATE submissions SET status = COALESCE(status, 'DRAFT');
UPDATE submissions SET content_json = COALESCE(content_json, '{}');
UPDATE submissions SET attachments_json = COALESCE(attachments_json, '[]');
UPDATE submissions SET checkpoints_json = COALESCE(checkpoints_json, '{}');
UPDATE submissions SET created_at = COALESCE(created_at, CURRENT_TIMESTAMP);
UPDATE submissions SET updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP);
UPDATE submissions SET status = UPPER(status);

-- evaluations
ALTER TABLE evaluations ADD COLUMN score_level VARCHAR(50);
ALTER TABLE evaluations ADD COLUMN score_numeric INTEGER;
ALTER TABLE evaluations ADD COLUMN dimension_scores_json JSON;
ALTER TABLE evaluations ADD COLUMN feedback TEXT;
ALTER TABLE evaluations ADD COLUMN evaluator_id INTEGER;
ALTER TABLE evaluations ADD COLUMN ai_generated BOOLEAN;
ALTER TABLE evaluations ADD COLUMN ai_suggestions_json JSON;
ALTER TABLE evaluations ADD COLUMN self_evaluation_json JSON;
ALTER TABLE evaluations ADD COLUMN peer_evaluation_json JSON;
ALTER TABLE evaluations ADD COLUMN is_anonymous BOOLEAN;
ALTER TABLE evaluations ADD COLUMN created_at DATETIME;

UPDATE evaluations SET evaluation_type = UPPER(evaluation_type);

CREATE INDEX IF NOT EXISTS idx_submissions_assignment_id ON submissions (assignment_id);
CREATE INDEX IF NOT EXISTS idx_submissions_student_id ON submissions (student_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_submission_id ON evaluations (submission_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_evaluator_id ON evaluations (evaluator_id);
CREATE INDEX IF NOT EXISTS idx_evaluations_type ON evaluations (evaluation_type);
