-- 005 — carry the API request id onto the job, so one render can be traced from
-- the client through the API into the worker and back (PRD §17 logging).

ALTER TABLE jobs ADD COLUMN request_id text;
