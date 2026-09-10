-- 004 — backoff for the render queue.
-- A job that failed a retryable way is scheduled to run again after `run_after`,
-- so the single worker backs off instead of hammering a struggling image model.

ALTER TABLE jobs ADD COLUMN run_after timestamptz NOT NULL DEFAULT now();

-- The worker scans for work that is queued (or a running job whose lease died)
-- and due. Replaces the plain queued index from 001.
DROP INDEX IF EXISTS jobs_queued_idx;
CREATE INDEX jobs_runnable_idx ON jobs (run_after)
    WHERE status IN ('queued', 'running');
