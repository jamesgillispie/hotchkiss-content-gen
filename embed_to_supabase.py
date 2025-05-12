#!/opt/homebrew/bin/python3
"""
Embedding Script for Supabase

This script fetches content from a Supabase 'pages' table, splits the content into chunks,
generates embeddings using OpenAI's API, and stores the chunks and embeddings in a 'pages_chunks' table.
"""

import os
import time
import json
from typing import List, Dict, Any, Optional
import requests
from tqdm import tqdm
from supabase import create_client, Client
from langchain.text_splitter import TokenTextSplitter

# Configuration
BATCH_SIZE = 100  # Number of embeddings to generate in a single API call

# Get environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_BASE = os.environ.get("OPENAI_API_BASE", "https://api.openai.com/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "text-embedding-ada-002")

# Validate environment variables
if not all([SUPABASE_URL, SUPABASE_KEY, OPENAI_API_KEY]):
    print("Error: Required environment variables are not set.")
    print("Please set: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, OPENAI_API_KEY")
    exit(1)

def connect_to_supabase() -> Client:
    """Connect to Supabase."""
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        exit(1)

def fetch_pages(supabase_client: Client) -> List[Dict[str, Any]]:
    """Fetch all records from the Supabase pages table."""
    try:
        # First check if the table exists
        try:
            print("Checking if 'pages' table exists...")
            test_response = supabase_client.table('pages').select('*').limit(1).execute()
            print(f"'pages' table exists and is accessible.")
        except Exception as table_error:
            print(f"Error checking 'pages' table: {table_error}")
            print("Please ensure the 'pages' table exists in your Supabase database.")
            return []
        
        # Fetch the actual data
        print("Fetching data from 'pages' table...")
        response = supabase_client.table('pages').select('url, markdown').execute()
        
        if hasattr(response, 'data'):
            if not response.data:
                print("Warning: 'pages' table exists but contains no data.")
            else:
                print(f"Successfully fetched {len(response.data)} records from 'pages' table.")
            return response.data
        
        print("Warning: Response has no 'data' attribute.")
        return []
    except Exception as e:
        print(f"Error fetching data from Supabase: {e}")
        import traceback
        traceback.print_exc()
        return []

def split_text(text: str) -> List[Dict[str, Any]]:
    """
    Split text into chunks using LangChain's TokenTextSplitter with tiktoken.
    Returns a list of dictionaries with 'text' and 'tokens' keys.
    Skips chunks with token count > 450.
    """
    if not text:
        return []
    
    # Initialize the text splitter with appropriate chunk size and overlap
    splitter = TokenTextSplitter(
        chunk_size=400,
        chunk_overlap=50,
        encoding_name="cl100k_base"  # fits ada-002 / text-embedding-3-small
    )
    
    # Split the text into chunks
    chunks = splitter.split_text(text)
    
    # Calculate token count for each chunk and filter out chunks with token count > 450
    result = []
    for chunk in chunks:
        # Get token count using the same tokenizer
        token_count = len(splitter._tokenizer.encode(chunk))
        
        # Skip chunks with token count > 450 (likely navigation menus, etc.)
        if token_count <= 450:
            result.append({
                'text': chunk,
                'tokens': token_count
            })
    
    return result

def create_embedding(texts: List[str], retries: int = 3) -> Optional[List[List[float]]]:
    """
    Create embeddings for a list of texts using OpenAI's API.
    Includes retry logic for rate limiting.
    """
    if not texts:
        return []
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    data = {
        "input": texts,
        "model": EMBED_MODEL
    }
    
    # Print debug info for the first attempt
    if retries == 3:  # First call
        print(f"Debug: Using OpenAI API at {OPENAI_API_BASE}")
        print(f"Debug: Using model: {EMBED_MODEL}")
    
    api_url = f"{OPENAI_API_BASE}/embeddings"
    
    for attempt in range(retries):
        try:
            # Print the URL we're trying to use
            print(f"Attempt {attempt+1}: Calling {api_url}")
            
            response = requests.post(
                api_url,
                headers=headers,
                json=data
            )
            
            if response.status_code == 200:
                # Success!
                print(f"Success with OpenAI API")
                result = response.json()
                return [item["embedding"] for item in result["data"]]
            
            if response.status_code == 429:  # Rate limit exceeded
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"Rate limit exceeded. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            # If we get here, there was an error
            print(f"OpenAI API returned status {response.status_code}")
            try:
                error_content = response.json()
                print(f"Response content: {json.dumps(error_content, indent=2)}")
            except:
                print(f"Response text: {response.text[:500]}")
            
            # If it's a server error, retry
            if response.status_code >= 500:
                if attempt < retries - 1:
                    wait_time = 2 ** attempt
                    print(f"Server error. Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                continue
            
            # For other errors, break the loop
            break
                
        except requests.exceptions.RequestException as e:
            print(f"Error with OpenAI API (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                wait_time = 2 ** attempt
                print(f"Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    print("Failed to create embeddings after multiple attempts.")
    return None

def ensure_pages_chunks_table(supabase_client: Client):
    """Ensure the pages_chunks table exists with the correct schema."""
    try:
        # Check if the table exists by querying it
        supabase_client.table('pages_chunks').select('*').limit(1).execute()
        print("Table 'pages_chunks' exists.")
    except Exception as e:
        print("Creating 'pages_chunks' table...")
        print("Please create the 'pages_chunks' table manually in the Supabase dashboard with the following SQL:")
        print("""
        -- Enable the pgvector extension
        CREATE EXTENSION IF NOT EXISTS vector;
        
        -- Create the pages_chunks table
        CREATE TABLE IF NOT EXISTS pages_chunks (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            content TEXT NOT NULL,
            tokens INTEGER NOT NULL,
            embedding vector(1536),
            UNIQUE(url, chunk_idx)
        );
        
        -- Create vector similarity search function
        create or replace function match_chunks(q vector, k int)
        returns table(url text, content text, score float)
        language sql stable as $$
        select url, content, 1 - (embedding <=> q) as score
        from pages_chunks
        order by embedding <=> q
        limit k;
        $$;
        """)
        print("After creating the table and function, please run this script again.")
        exit(1)

def upsert_chunks(supabase_client: Client, chunks_data: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert chunks and embeddings to the pages_chunks table.
    Returns a dictionary with success and error counts.
    """
    if not chunks_data:
        return {"success": 0, "error": 0}
    
    success_count = 0
    error_count = 0
    
    try:
        # Print debug info about the first chunk
        if chunks_data:
            print(f"Debug: Upserting {len(chunks_data)} chunks")
            print(f"Debug: First chunk URL: {chunks_data[0]['url']}")
            print(f"Debug: First chunk index: {chunks_data[0]['chunk_idx']}")
            print(f"Debug: First chunk token count: {chunks_data[0]['tokens']}")
            print(f"Debug: First chunk embedding length: {len(chunks_data[0]['embedding'])}")
        
        # Upsert data (insert if not exists, update if exists)
        result = supabase_client.table('pages_chunks').upsert(
            chunks_data, 
            on_conflict=('url, chunk_idx')
        ).execute()
        
        # Check if the operation was successful
        if hasattr(result, 'data'):
            print(f"Debug: Upsert successful, response data length: {len(result.data)}")
            success_count = len(chunks_data)
        else:
            print(f"Debug: Upsert response has no data attribute")
            print(f"Debug: Upsert response: {result}")
            error_count = len(chunks_data)
            
    except Exception as e:
        error_count = len(chunks_data)
        print(f"Error upserting chunks: {e}")
        # Print the full exception traceback for debugging
        import traceback
        traceback.print_exc()
    
    return {
        "success": success_count,
        "error": error_count
    }

def check_pages_chunks_table(supabase_client: Client) -> int:
    """Check if the pages_chunks table has data and return the count."""
    try:
        print("Checking count in 'pages_chunks' table...")
        # Get all records and count them
        response = supabase_client.table('pages_chunks').select('id').execute()
        
        if hasattr(response, 'data'):
            count = len(response.data)
            print(f"Found {count} records in 'pages_chunks' table.")
            return count
        
        print("Warning: Response has no 'data' attribute.")
        return 0
    except Exception as e:
        print(f"Error checking pages_chunks table: {e}")
        import traceback
        traceback.print_exc()
        return 0

def clear_pages_chunks_table(supabase_client: Client) -> bool:
    """Clear all data from the pages_chunks table."""
    try:
        print("Clearing 'pages_chunks' table...")
        # Delete all records from the table
        response = supabase_client.table('pages_chunks').delete().execute()
        
        if hasattr(response, 'data'):
            print(f"Successfully cleared 'pages_chunks' table.")
            return True
        
        print("Warning: Response has no 'data' attribute.")
        return False
    except Exception as e:
        print(f"Error clearing pages_chunks table: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function to orchestrate the embedding process."""
    start_time = time.time()
    
    # Connect to Supabase
    supabase_client = connect_to_supabase()
    
    # Ensure the pages_chunks table exists
    ensure_pages_chunks_table(supabase_client)
    
    # Clear the pages_chunks table before starting
    clear_pages_chunks_table(supabase_client)
    
    # Check if the pages_chunks table already has data (should be 0 after clearing)
    initial_chunks_count = check_pages_chunks_table(supabase_client)
    print(f"Current count in pages_chunks table: {initial_chunks_count}")
    
    # Fetch pages from Supabase
    print("Fetching pages from Supabase...")
    pages = fetch_pages(supabase_client)
    
    if not pages:
        print("No pages found in Supabase. Exiting.")
        return
    
    print(f"Found {len(pages)} pages in Supabase.")
    
    # Process pages
    total_pages_processed = 0
    total_chunks_embedded = 0
    total_tokens = 0
    total_errors = 0
    
    for i in tqdm(range(0, len(pages), BATCH_SIZE), desc="Processing pages"):
        batch = pages[i:i+BATCH_SIZE]
        
        for page in batch:
            url = page.get('url')
            markdown = page.get('markdown', '')
            
            if not url or not markdown:
                continue
            
            # Split the markdown into chunks
            chunk_objects = split_text(markdown)
            
            if not chunk_objects:
                continue
            
            # Extract just the text for embedding
            chunks = [chunk_obj['text'] for chunk_obj in chunk_objects]
            token_counts = [chunk_obj['tokens'] for chunk_obj in chunk_objects]
            
            page_total_tokens = sum(token_counts)
            
            # Process chunks in batches for embedding
            chunks_embedded = 0
            for j in range(0, len(chunks), BATCH_SIZE):
                chunk_batch = chunks[j:j+BATCH_SIZE]
                token_batch = token_counts[j:j+BATCH_SIZE]
                
                # Generate embeddings for the chunk batch
                embeddings = create_embedding(chunk_batch)
                
                if not embeddings:
                    total_errors += len(chunk_batch)
                    continue
                
                # Prepare data for upserting
                chunks_data = []
                for k, (chunk, token_count, embedding) in enumerate(zip(chunk_batch, token_batch, embeddings)):
                    chunk_idx = j + k
                    chunks_data.append({
                        'url': url,
                        'chunk_idx': chunk_idx,
                        'content': chunk,
                        'tokens': token_count,
                        'embedding': embedding
                    })
                
                # Upsert chunks to Supabase
                result = upsert_chunks(supabase_client, chunks_data)
                
                chunks_embedded += result['success']
                total_errors += result['error']
            
            # Per-page logging
            print(f"{url} → {len(chunk_objects)} chunks, {page_total_tokens} tokens")
            
            total_chunks_embedded += chunks_embedded
            total_tokens += page_total_tokens
            total_pages_processed += 1
    
    # Calculate estimated cost
    estimated_cost = (total_tokens / 1000) * 0.0001
    
    # Check final count in pages_chunks table
    final_chunks_count = check_pages_chunks_table(supabase_client)
    chunks_added = final_chunks_count - initial_chunks_count
    
    # Print summary
    elapsed_time = time.time() - start_time
    print("\n" + "="*50)
    print("EMBEDDING SUMMARY")
    print("="*50)
    print(f"Total pages processed: {total_pages_processed}")
    print(f"Total chunks embedded: {total_chunks_embedded}")
    print(f"Total tokens: {total_tokens}")
    print(f"Estimated cost: ${estimated_cost:.4f}")
    print(f"Errors: {total_errors}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print("="*50)
    print(f"Initial count in pages_chunks table: {initial_chunks_count}")
    print(f"Final count in pages_chunks table: {final_chunks_count}")
    print(f"Net chunks added: {chunks_added}")
    print("="*50)
    
    if total_errors > 0:
        print("\nWarning: Some chunks failed to process. Check the logs above for details.")
    elif chunks_added == 0:
        print("\nWarning: No new chunks were added to the pages_chunks table.")
        print("This could be due to:")
        print("1. All chunks already existed in the table (with the same URLs and chunk_idx)")
        print("2. There was an issue with the upsert operation")
        print("3. The pages table was empty or contained no valid content")
    else:
        print(f"\nSuccess: {chunks_added} chunks were added to the pages_chunks table!")

if __name__ == "__main__":
    main()
