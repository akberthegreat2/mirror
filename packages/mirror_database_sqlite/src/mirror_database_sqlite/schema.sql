-- Mirror Database SQLite Schema
-- DDL for all 11 control-plane entity tables

-- ============================================================================
-- Projects
-- ============================================================================
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_projects_slug ON projects(slug);
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);

-- ============================================================================
-- Pipelines
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipelines (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    project_id TEXT NOT NULL,
    slug TEXT NOT NULL,
    name TEXT NOT NULL,
    origin TEXT NOT NULL DEFAULT 'local',
    is_read_only INTEGER NOT NULL DEFAULT 0,
    source_ref TEXT,
    source_hash TEXT,
    definition_ref TEXT,
    current_version_number INTEGER NOT NULL DEFAULT 0,
    current_version_hash TEXT,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipelines_project_id ON pipelines(project_id);
CREATE INDEX IF NOT EXISTS idx_pipelines_slug ON pipelines(project_id, slug);
CREATE INDEX IF NOT EXISTS idx_pipelines_origin ON pipelines(origin);

-- ============================================================================
-- Pipeline Versions
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_versions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    definition_ref TEXT NOT NULL,
    definition_hash TEXT NOT NULL,
    definition_format TEXT NOT NULL DEFAULT 'json',
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_pipeline_versions_pipeline_version ON pipeline_versions(pipeline_id, version);
CREATE INDEX IF NOT EXISTS idx_pipeline_versions_pipeline_id ON pipeline_versions(pipeline_id);

-- ============================================================================
-- Execution Runs
-- ============================================================================
CREATE TABLE IF NOT EXISTS execution_runs (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    pipeline_version INTEGER NOT NULL,
    run_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending',
    execution_class TEXT NOT NULL DEFAULT 'default',
    worker_id TEXT,
    inputs TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_runs_pipeline_id ON execution_runs(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_execution_runs_run_id ON execution_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_execution_runs_status ON execution_runs(status);
CREATE INDEX IF NOT EXISTS idx_execution_runs_execution_class ON execution_runs(execution_class);
CREATE INDEX IF NOT EXISTS idx_execution_runs_worker_id ON execution_runs(worker_id);

-- ============================================================================
-- Execution Steps
-- ============================================================================
CREATE TABLE IF NOT EXISTS execution_steps (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    capability TEXT NOT NULL,
    provider TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    inputs TEXT NOT NULL DEFAULT '{}',
    error TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    FOREIGN KEY (run_id) REFERENCES execution_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_execution_steps_run_id ON execution_steps(run_id);
CREATE INDEX IF NOT EXISTS idx_execution_steps_status ON execution_steps(status);

-- ============================================================================
-- Workers
-- ============================================================================
CREATE TABLE IF NOT EXISTS workers (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    worker_id TEXT NOT NULL UNIQUE,
    backend TEXT NOT NULL,
    execution_class TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    heartbeat_at TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_workers_worker_id ON workers(worker_id);
CREATE INDEX IF NOT EXISTS idx_workers_execution_class ON workers(execution_class);
CREATE INDEX IF NOT EXISTS idx_workers_status ON workers(status);
CREATE INDEX IF NOT EXISTS idx_workers_heartbeat_at ON workers(heartbeat_at);

-- ============================================================================
-- Schedules
-- ============================================================================
CREATE TABLE IF NOT EXISTS schedules (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    name TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    cron TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    next_run_at TEXT,
    status TEXT NOT NULL DEFAULT 'enabled',
    max_concurrency INTEGER NOT NULL DEFAULT 1,
    metadata TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (pipeline_id) REFERENCES pipelines(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_schedules_pipeline_id ON schedules(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_schedules_status ON schedules(status);
CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled);
CREATE INDEX IF NOT EXISTS idx_schedules_next_run_at ON schedules(next_run_at);

-- ============================================================================
-- Crawled URLs
-- ============================================================================
CREATE TABLE IF NOT EXISTS crawled_urls (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pipeline_id TEXT,
    run_id TEXT,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'discovered',
    discovered_at TEXT NOT NULL,
    crawled_at TEXT,
    error TEXT,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_crawled_urls_pipeline_id ON crawled_urls(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_crawled_urls_run_id ON crawled_urls(run_id);
CREATE INDEX IF NOT EXISTS idx_crawled_urls_status ON crawled_urls(status);
CREATE INDEX IF NOT EXISTS idx_crawled_urls_url ON crawled_urls(url);

-- ============================================================================
-- Archive Records
-- ============================================================================
CREATE TABLE IF NOT EXISTS archive_records (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    pipeline_id TEXT,
    run_id TEXT,
    resource_key TEXT NOT NULL,
    storage_ref TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    content_type TEXT,
    content_length INTEGER,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_archive_records_pipeline_id ON archive_records(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_archive_records_run_id ON archive_records(run_id);
CREATE INDEX IF NOT EXISTS idx_archive_records_content_hash ON archive_records(content_hash);

-- ============================================================================
-- Checkpoints
-- ============================================================================
CREATE TABLE IF NOT EXISTS checkpoints (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    payload TEXT NOT NULL DEFAULT '{}',
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_run_id ON checkpoints(run_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_run_step ON checkpoints(run_id, step_id);

-- ============================================================================
-- Dead Letters
-- ============================================================================
CREATE TABLE IF NOT EXISTS dead_letters (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    run_id TEXT NOT NULL,
    pipeline_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    terminal_status TEXT NOT NULL,
    reason TEXT NOT NULL,
    original_inputs TEXT NOT NULL DEFAULT '{}',
    policy_state TEXT NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL DEFAULT '{}',
    retry_count INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_dead_letters_pipeline_id ON dead_letters(pipeline_id);
CREATE INDEX IF NOT EXISTS idx_dead_letters_run_id ON dead_letters(run_id);
CREATE INDEX IF NOT EXISTS idx_dead_letters_terminal_status ON dead_letters(terminal_status);

-- ============================================================================
-- SQLite pragmas for better concurrency
-- ============================================================================
-- WAL mode is enabled in the connection setup, not here
-- PRAGMA journal_mode = WAL;
-- PRAGMA synchronous = NORMAL;
-- PRAGMA busy_timeout = 5000;
-- PRAGMA temp_store = MEMORY;