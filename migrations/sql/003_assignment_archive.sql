ALTER TABLE assignments ADD COLUMN is_archived BOOLEAN;
ALTER TABLE assignments ADD COLUMN archived_at DATETIME;

UPDATE assignments SET is_archived = COALESCE(is_archived, 0);

CREATE INDEX IF NOT EXISTS idx_assignments_archived ON assignments (is_archived);
