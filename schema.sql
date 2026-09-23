-- Instaretto schema
--
-- This is a plain SQL script, not a migration tool. Read it top to bottom.
-- It's safe to run more than once against the same database -- every
-- statement below is written to be idempotent, so re-running it (say,
-- because you're not sure you already ran it) never duplicates anything
-- or errors out.

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS posts (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- S3 object key only. The image bytes live in S3, never here.
    s3_key      TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Feed is always "newest first", so index the column we sort by.
CREATE INDEX IF NOT EXISTS idx_posts_created_at ON posts (created_at DESC);

CREATE TABLE IF NOT EXISTS likes (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id    INTEGER NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- One like per (user, post). The app relies on this constraint
    -- to reject a double-like instead of checking for one itself --
    -- see LAB.md Part 4.
    PRIMARY KEY (user_id, post_id)
);

-- ---------------------------------------------------------------------
-- Seed data
-- ---------------------------------------------------------------------
-- Only seeds on a genuinely empty database. Posts and likes have no
-- natural unique key to guard a plain INSERT with (unlike users, which
-- ON CONFLICT (email) DO NOTHING could protect on its own) -- so the
-- whole block is gated on "no users yet" instead, which is exactly the
-- condition a fresh database is actually in.
--
-- Password for both seed users is: password123
-- Hash was generated with:
--   werkzeug.security.generate_password_hash("password123", method="pbkdf2:sha256")
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM users) THEN
        INSERT INTO users (email, password_hash) VALUES
            ('alice@example.com', 'pbkdf2:sha256:1000000$VD0jOCikI0fJeUXn$cdc308da378688a9f1c7bcdfdd3782d658a108c8146b533834af7f6c8da2357d'),
            ('bob@example.com',   'pbkdf2:sha256:1000000$VD0jOCikI0fJeUXn$cdc308da378688a9f1c7bcdfdd3782d658a108c8146b533834af7f6c8da2357d');

        -- These s3_key values are placeholders -- no such objects exist
        -- in your bucket yet. The feed will show a broken-image icon for
        -- them until you upload real pictures through the app in
        -- LAB.md Part 3. That's expected and is itself worth noticing:
        -- the row exists happily in the database with no idea whether
        -- the object behind its key is actually there.
        INSERT INTO posts (user_id, s3_key, description) VALUES
            (1, 'posts/seed-placeholder-1.jpg', 'Seed post from Alice (placeholder, no real image yet)'),
            (2, 'posts/seed-placeholder-2.jpg', 'Seed post from Bob (placeholder, no real image yet)');

        INSERT INTO likes (user_id, post_id) VALUES
            (2, 1);
    END IF;
END $$;
