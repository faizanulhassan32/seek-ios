-- Migration: Add answer-related columns to persons table
-- Date: 2025-11-19
-- Description: Adds support for AI-generated answers and related questions

-- Add answer column (stores AI-generated biographical text)
ALTER TABLE persons ADD COLUMN IF NOT EXISTS answer TEXT;

-- Add related_questions column (stores array of related question strings)
ALTER TABLE persons ADD COLUMN IF NOT EXISTS related_questions JSONB;

-- Add answer_generated_at column (timestamp of when answer was generated)
ALTER TABLE persons ADD COLUMN IF NOT EXISTS answer_generated_at TIMESTAMP WITH TIME ZONE;
