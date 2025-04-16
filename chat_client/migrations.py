"""
Migrations
"""

create_base_install = """
-- users table
CREATE TABLE users (
  user_id INTEGER PRIMARY KEY,
  password_hash TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  created TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  verified INTEGER DEFAULT 0,
  random TEXT NOT NULL,
  locked INTEGER DEFAULT 0
) STRICT;

-- Indexes for users table
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_random ON users(random);
CREATE INDEX idx_users_password_hash ON users(password_hash);

-- user_token is used with session management
CREATE TABLE user_token (
  user_token_id INTEGER PRIMARY KEY,
  token TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  last_login TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  expires INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES user(id)
) STRICT;

-- Indexes for user_tokens table
CREATE INDEX idx_user_token_user_id ON user_token(user_id);
CREATE INDEX idx_user_token_token ON user_token(token);

-- token table for reset password and verify account
CREATE TABLE token (
  token_id INTEGER PRIMARY KEY,
  token TEXT NOT NULL,
  type TEXT NOT NULL,
  created TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
) STRICT;

CREATE TABLE acl (
  acl_id INTEGER PRIMARY KEY,
  role TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  entity_id INTEGER DEFAULT NULL, -- Only needed if permissions apply to specific objects
  FOREIGN KEY (user_id) REFERENCES user(id)
) STRICT;

-- Indexes for acl table
CREATE INDEX idx_acl_user_id ON acl(user_id);
CREATE INDEX idx_acl_role ON acl(role);
CREATE INDEX idx_acl_entity_id ON acl(entity_id);

CREATE TABLE cache (
  cache_id INTEGER PRIMARY KEY,
  key TEXT NOT NULL,
  value TEXT,
  unix_timestamp INTEGER DEFAULT 0
) STRICT;

--- Indexes for cache
CREATE INDEX idx_cache_key ON cache(key);

-- dialog table
CREATE TABLE dialog (
  dialog_id TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  created TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  public INTEGER DEFAULT 0,
  FOREIGN KEY (user_id) REFERENCES user(id)
) STRICT;

-- message table with ON DELETE CASCADE
CREATE TABLE message (
  message_id INTEGER PRIMARY KEY,
  dialog_id TEXT NOT NULL,
  user_id INTEGER NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  created TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
  FOREIGN KEY (dialog_id) REFERENCES dialog(dialog_id) ON DELETE CASCADE,
  FOREIGN KEY (user_id) REFERENCES user(id)
) STRICT;

-- indexes for faster lookups
CREATE INDEX dialog_user_id ON dialog(user_id);
CREATE INDEX message_dialog_id ON message(dialog_id);
CREATE INDEX message_user_id ON message(user_id);

"""

# List of migrations with keys
migrations = {
    "create_base_install": create_base_install,
}
