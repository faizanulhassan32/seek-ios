#!/usr/bin/env python3
"""
Database setup script for Person Search app
Runs the schemas.sql file against Supabase
"""

import os
from dotenv import load_dotenv
from supabase import create_client

# Load environment variables
load_dotenv()

def setup_database():
    """Set up the database by running the SQL schema"""

    # Get credentials
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_KEY')

    if not url or not key:
        print("❌ Error: SUPABASE_URL and SUPABASE_KEY must be set in .env file")
        return False

    print(f"🔗 Connecting to Supabase at {url}...")

    try:
        # Create Supabase client
        supabase = create_client(url, key)

        # Read the SQL file
        print("📄 Reading schemas.sql...")
        with open('db/schemas.sql', 'r') as f:
            sql_content = f.read()

        # Split into individual statements
        statements = [stmt.strip() for stmt in sql_content.split(';') if stmt.strip()]

        print(f"📊 Executing {len(statements)} SQL statements...")

        # Execute each statement using Supabase's RPC or direct SQL
        # Note: Supabase Python client doesn't have direct SQL execution
        # So we'll use the REST API directly
        from supabase._sync.client import SyncClient

        # For Supabase, we need to use the PostgREST API or use psycopg2
        # Let's try using psycopg2 if available
        try:
            import psycopg2

            # Extract database connection string from Supabase URL
            # Supabase connection string format:
            # postgresql://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres

            print("\n⚠️  To run SQL directly, we need your database password.")
            print("You can find it in Supabase Dashboard > Settings > Database > Connection string")
            print("\nAlternatively, run the SQL manually in the Supabase SQL Editor.")
            print("\nOr provide the full PostgreSQL connection string:")

            conn_string = input("PostgreSQL connection string (or press Enter to skip): ").strip()

            if conn_string:
                print("\n🔄 Connecting to database...")
                conn = psycopg2.connect(conn_string)
                cur = conn.cursor()

                for i, statement in enumerate(statements, 1):
                    if statement:
                        print(f"  Executing statement {i}/{len(statements)}...")
                        cur.execute(statement)

                conn.commit()
                cur.close()
                conn.close()

                print("\n✅ Database setup completed successfully!")
                print("✅ Tables created: users, persons, chats")
                return True
            else:
                print("\n📋 Please run the following SQL in Supabase SQL Editor:")
                print("=" * 60)
                print(sql_content)
                print("=" * 60)
                return False

        except ImportError:
            print("\n⚠️  psycopg2 not installed. Installing...")
            print("\nRun: pip install psycopg2-binary")
            print("\nOr run the SQL manually in Supabase SQL Editor:")
            print("=" * 60)
            print(sql_content)
            print("=" * 60)
            return False

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Person Search App - Database Setup")
    print("=" * 60)
    print()

    setup_database()
