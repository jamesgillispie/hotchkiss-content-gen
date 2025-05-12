#!/usr/bin/env python3
"""
SQLite to Supabase Migration Script

This script reads data from a local SQLite database and uploads it to a Supabase Postgres table.
It handles batch inserts and upserts (updates existing records instead of inserting duplicates).
"""

import os
import sqlite3
import time
from typing import List, Dict, Any
from supabase import create_client, Client

# Configuration
SQLITE_DB_PATH = "hotchkiss_content.db"
BATCH_SIZE = 100  # Number of records to insert in a single batch

# Get Supabase credentials from environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set.")
    exit(1)

def connect_to_sqlite() -> sqlite3.Connection:
    """Connect to the SQLite database."""
    try:
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row  # This enables column access by name
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to SQLite database: {e}")
        exit(1)

def connect_to_supabase() -> Client:
    """Connect to Supabase."""
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        exit(1)

def fetch_sqlite_data(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Fetch all records from the SQLite pages table."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT url, title, markdown, crawled_at FROM pages")
        rows = cursor.fetchall()
        # Convert rows to list of dictionaries
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"Error fetching data from SQLite: {e}")
        return []

def upload_to_supabase(supabase_client: Client, data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upload data to Supabase in batches.
    Returns a dictionary with success and error counts.
    """
    total_records = len(data)
    success_count = 0
    error_count = 0
    
    print(f"Starting migration of {total_records} records to Supabase...")
    
    # Process in batches
    for i in range(0, total_records, BATCH_SIZE):
        batch = data[i:i+BATCH_SIZE]
        batch_size = len(batch)
        
        try:
            # Upsert data (insert if not exists, update if exists)
            result = supabase_client.table('pages').upsert(batch).execute()
            
            # Check if the operation was successful
            if hasattr(result, 'data'):
                success_count += batch_size
                print(f"Batch {i//BATCH_SIZE + 1}: Successfully uploaded {batch_size} records")
            else:
                error_count += batch_size
                print(f"Batch {i//BATCH_SIZE + 1}: Error uploading {batch_size} records")
                
        except Exception as e:
            error_count += batch_size
            print(f"Batch {i//BATCH_SIZE + 1}: Error uploading {batch_size} records: {e}")
        
        # Small delay to avoid overwhelming the API
        time.sleep(0.5)
    
    return {
        "total": total_records,
        "success": success_count,
        "error": error_count
    }

def main():
    """Main function to orchestrate the migration process."""
    start_time = time.time()
    
    # Connect to databases
    sqlite_conn = connect_to_sqlite()
    supabase_client = connect_to_supabase()
    
    # Fetch data from SQLite
    print("Fetching data from SQLite database...")
    data = fetch_sqlite_data(sqlite_conn)
    
    if not data:
        print("No data found in SQLite database. Exiting.")
        sqlite_conn.close()
        return
    
    print(f"Found {len(data)} records in SQLite database.")
    
    # Upload data to Supabase
    results = upload_to_supabase(supabase_client, data)
    
    # Close SQLite connection
    sqlite_conn.close()
    
    # Print summary
    elapsed_time = time.time() - start_time
    print("\n" + "="*50)
    print("MIGRATION SUMMARY")
    print("="*50)
    print(f"Total records processed: {results['total']}")
    print(f"Successfully uploaded: {results['success']}")
    print(f"Failed to upload: {results['error']}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print("="*50)
    
    if results['error'] > 0:
        print("\nWarning: Some records failed to upload. Check the logs above for details.")
    else:
        print("\nSuccess: All records were uploaded successfully!")

if __name__ == "__main__":
    main()
