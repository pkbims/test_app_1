-- 007 — the options round (options_review/HANDOFF.md §3, §4.8).
--
-- Room type detection, plus the five style-screen options (walls, furniture,
-- decor, plants, palette). Every new `renders` column mirrors a `RenderCreate`
-- field 1:1, stored with the render's own default so history is self-describing
-- even for renders submitted before a client sends the field explicitly.
-- `inventories.room_type` is the vision call's detected guess, separate from
-- `renders.room_type` (the resolved value actually used — request override, else
-- detected, else null; see HANDOFF §3.4).

ALTER TABLE inventories ADD COLUMN room_type text
    CHECK (room_type IS NULL OR room_type IN (
        'living_room', 'bedroom', 'kitchen', 'dining_room', 'home_office',
        'kids_room', 'nursery', 'bathroom', 'hallway', 'studio', 'workshop',
        'server_room'
    ));

ALTER TABLE renders ADD COLUMN room_type text
    CHECK (room_type IS NULL OR room_type IN (
        'living_room', 'bedroom', 'kitchen', 'dining_room', 'home_office',
        'kids_room', 'nursery', 'bathroom', 'hallway', 'studio', 'workshop',
        'server_room'
    ));
ALTER TABLE renders ADD COLUMN walls text NOT NULL DEFAULT 'leave'
    CHECK (walls IN ('repaint', 'leave'));
ALTER TABLE renders ADD COLUMN furniture text NOT NULL DEFAULT 'keep_only'
    CHECK (furniture IN ('keep_only', 'add'));
ALTER TABLE renders ADD COLUMN add_furniture jsonb NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE renders ADD COLUMN decor text NOT NULL DEFAULT 'as_style'
    CHECK (decor IN ('minimal', 'as_style', 'plenty'));
ALTER TABLE renders ADD COLUMN plants boolean NOT NULL DEFAULT false;
ALTER TABLE renders ADD COLUMN palette text NOT NULL DEFAULT 'as_style'
    CHECK (palette IN ('as_style', 'neutral', 'warm', 'cool', 'bold'));
