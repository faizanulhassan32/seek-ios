#!/usr/bin/env python3
"""
Migration runner script for Person Search app
Runs migration SQL files against Supabase
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_migration(migration_file):
    """Run a migration SQL file"""

    # Get credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        return False

    print(f"🔗 Connecting to Supabase at {url}...")

    try:
        # Read the migration file
        print(f"📄 Reading {migration_file}...")
        with open(migration_file, 'r') as f:
            sql_content = f.read()

        # Check if psycopg2 is available
        try:
            import psycopg2

            print("\n⚠️  To run migrations, we need your database password.")
            print("You can find it in Supabase Dashboard > Settings > Database > Connection string")
            print("\nAlternatively, you can copy the SQL below and run it in the Supabase SQL Editor.")
            print("\nProvide the full PostgreSQL connection string:")

            conn_string = input("PostgreSQL connection string (or press Enter to view SQL): ").strip()

            if conn_string:
                print("\n🔄 Running migration...")
                conn = psycopg2.connect(conn_string)
                cur = conn.cursor()

                # Execute the migration
                cur.execute(sql_content)

                conn.commit()
                cur.close()
                conn.close()

                print("\n✅ Migration completed successfully!")
                return True
            else:
                print("\n📋 Copy and run the following SQL in Supabase SQL Editor:")
                print("=" * 80)
                print(sql_content)
                print("=" * 80)
                print("\nTo run in Supabase:")
                print("1. Go to your Supabase project dashboard")
                print("2. Navigate to SQL Editor")
                print("3. Create a new query")
                print("4. Paste the SQL above")
                print("5. Click 'Run'")
                return False

        except ImportError:
            print("\n⚠️  psycopg2 not installed.")
            print("\n📋 Copy and run the following SQL in Supabase SQL Editor:")
            print("=" * 80)
            print(sql_content)
            print("=" * 80)
            print("\nTo run in Supabase:")
            print("1. Go to your Supabase project dashboard")
            print("2. Navigate to SQL Editor")
            print("3. Create a new query")
            print("4. Paste the SQL above")
            print("5. Click 'Run'")
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 80)
    print("Person Search App - Migration Runner")
    print("=" * 80)
    print()

    # Check for migration file argument
    if len(sys.argv) > 1:
        migration_file = sys.argv[1]
    else:
        migration_file = 'db/migrations/001_add_answer_columns.sql'

    if not os.path.exists(migration_file):
        print(f"❌ Error: Migration file not found: {migration_file}")
        sys.exit(1)

    run_migration(migration_file)
