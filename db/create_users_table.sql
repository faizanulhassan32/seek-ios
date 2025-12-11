-- Drop existing table if it exists (to ensure clean state)
DROP TABLE IF EXISTS users CASCADE;

-- Create users table for Apple Sign In
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    apple_id TEXT UNIQUE NOT NULL,
    email TEXT,
    full_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on apple_id for faster lookups
CREATE INDEX idx_users_apple_id ON users(apple_id);

-- Enable Row Level Security (RLS)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Create policy to allow all operations (adjust as needed for production)
CREATE POLICY "Enable all access for users" ON users
    FOR ALL
    USING (true)
    WITH CHECK (true);
