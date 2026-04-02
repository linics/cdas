CREATE TABLE IF NOT EXISTS submission_attachment_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id INTEGER NOT NULL,
    uploader_id INTEGER NOT NULL,
    source VARCHAR(20) NOT NULL DEFAULT 'upload',
    original_filename VARCHAR(255) NOT NULL,
    storage_path VARCHAR(512) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes INTEGER,
    parsing_status VARCHAR(20) NOT NULL DEFAULT 'uploaded',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
    FOREIGN KEY (uploader_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submission_attachment_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attachment_id INTEGER NOT NULL UNIQUE,
    extracted_text TEXT,
    summary_text TEXT,
    error_msg TEXT,
    analyzed_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (attachment_id) REFERENCES submission_attachment_assets(id) ON DELETE CASCADE
);
