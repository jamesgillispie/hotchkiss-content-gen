# SQLite to Supabase Migration Tool

This tool migrates data from a local SQLite database (`hotchkiss_content.db`) to a Supabase Postgres database.

## Prerequisites

- Python 3.6+
- `supabase-py` library
- SQLite database with the required schema
- Supabase project with a `pages` table

## Setup

1. Install the required Python package:
   ```
   pip install supabase
   ```

2. Set up environment variables for Supabase authentication:
   ```bash
   # For macOS/Linux
   export SUPABASE_URL="https://rfsopqrtbqbgqntaeaut.supabase.co"
   export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
   
   # For Windows Command Prompt
   set SUPABASE_URL=https://rfsopqrtbqbgqntaeaut.supabase.co
   set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
   
   # For Windows PowerShell
   $env:SUPABASE_URL = "https://rfsopqrtbqbgqntaeaut.supabase.co"
   $env:SUPABASE_SERVICE_ROLE_KEY = "your-service-role-key"
   ```

   Note: You need to use the service role key (not the anon key) for database operations.

## Usage

Run the migration script:

```bash
python migrate_to_supabase.py
```

The script will:
1. Connect to the local SQLite database
2. Read all records from the `pages` table
3. Upload the data to Supabase in batches
4. Handle upserts (update if record exists)
5. Print a summary of the migration results

## Database Schema

The script expects the following schema in both the SQLite and Supabase databases:

```sql
CREATE TABLE pages (
  url TEXT PRIMARY KEY,
  title TEXT,
  markdown TEXT,
  crawled_at INTEGER
);
```

## Configuration

You can modify the following settings in the script:

- `SQLITE_DB_PATH`: Path to the SQLite database file
- `BATCH_SIZE`: Number of records to insert in a single batch
