-- 006 — persist the exact prompt text sent to each OpenAI call, for review.
--
-- Previously only the user's own free-text input (renders.prompt) was stored;
-- the constructed text actually sent to the model was built in memory and
-- discarded. These columns capture it verbatim, so it can be inspected and
-- iterated on later. DB-only — not part of the contract, not exposed by any
-- route. Rides along the existing ON DELETE CASCADE from rooms, so deleting a
-- room deletes these too, same as the photos and images already do.

ALTER TABLE inventories ADD COLUMN prompt text;
ALTER TABLE renders ADD COLUMN generation_prompt text;
ALTER TABLE renders ADD COLUMN preservation_prompt text;
