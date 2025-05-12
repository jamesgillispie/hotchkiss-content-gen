#!/usr/bin/env python3
"""
Embedding Generation Script for Hotchkiss Content

This script:
1. Reads markdown content from the Supabase 'pages' table
2. Splits the content into chunks of approximately 400 tokens
3. Generates embeddings using OpenAI's text-embedding-3-small model
4. Upserts the chunks and embeddings into a 'pages_chunks' table in Supabase
"""

import os
import time
import re
import tiktoken
import numpy as np
from typing import List, Dict, Any, Tuple
from openai import OpenAI
from supabase import create_client, Client

# Configuration
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
BATCH_SIZE = 10  # Number of pages to process in a single batch
EMBEDDING_MODEL = "text-embedding-3-small"
TARGET_TOKENS_PER_CHUNK = 400
MAX_TOKENS_PER_CHUNK = 500  # Maximum tokens per chunk to avoid exceeding limits

# Initialize tokenizer for text-embedding-3-small
tokenizer = tiktoken.get_encoding("cl100k_base")  # This is the encoding used by text-embedding-3-small

def connect_to_supabase() -> Client:
    """Connect to Supabase."""
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        exit(1)

def connect_to_openai() -> OpenAI:
    """Connect to OpenAI API."""
    try:
        return OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        print(f"Error connecting to OpenAI: {e}")
        exit(1)

def fetch_pages(supabase_client: Client) -> List[Dict[str, Any]]:
    """Fetch all pages from Supabase."""
    try:
        response = supabase_client.table('pages').select('url, markdown').execute()
        return response.data
    except Exception as e:
        print(f"Error fetching pages from Supabase: {e}")
        return []

def create_pages_chunks_table_if_not_exists(supabase_client: Client):
    """Create the pages_chunks table if it doesn't exist."""
    try:
        # Check if the table exists
        response = supabase_client.table('pages_chunks').select('url', count='exact').limit(1).execute()
        print("pages_chunks table already exists.")
    except Exception:
        print("Creating pages_chunks table...")
        # Create the table with the pgvector extension
        query = """
        -- Enable pgvector extension if not already enabled
        CREATE EXTENSION IF NOT EXISTS vector;
        
        -- Create the pages_chunks table
        CREATE TABLE IF NOT EXISTS pages_chunks (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            chunk_idx INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding vector(1536),  -- text-embedding-3-small produces 1536-dimensional vectors
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(url, chunk_idx)
        );
        
        -- Create an index for faster similarity searches
        CREATE INDEX IF NOT EXISTS pages_chunks_url_idx ON pages_chunks(url);
        """
        supabase_client.query(query).execute()
        print("pages_chunks table created successfully.")

def split_text_into_chunks(text: str) -> List[str]:
    """
    Split text into chunks of approximately TARGET_TOKENS_PER_CHUNK tokens.
    Uses a simple paragraph-based approach to maintain context.
    """
    if not text or text.strip() == "":
        return []
    
    # Clean the text
    text = text.replace('\r', '')
    
    # Split by paragraphs first
    paragraphs = re.split(r'\n\s*\n', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    chunks = []
    current_chunk = []
    current_token_count = 0
    
    for paragraph in paragraphs:
        # Tokenize the paragraph
        paragraph_tokens = tokenizer.encode(paragraph)
        paragraph_token_count = len(paragraph_tokens)
        
        # If adding this paragraph would exceed the maximum, start a new chunk
        if current_token_count + paragraph_token_count > MAX_TOKENS_PER_CHUNK and current_chunk:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_token_count = 0
        
        # Add the paragraph to the current chunk
        current_chunk.append(paragraph)
        current_token_count += paragraph_token_count
        
        # If we're close to or above the target token count, start a new chunk
        if current_token_count >= TARGET_TOKENS_PER_CHUNK:
            chunks.append(" ".join(current_chunk))
            current_chunk = []
            current_token_count = 0
    
    # Add any remaining content as the last chunk
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    
    return chunks

def generate_embedding(client: OpenAI, text: str) -> List[float]:
    """Generate an embedding for the given text using OpenAI's API."""
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error generating embedding: {e}")
        # Return a zero vector as a fallback
        return [0.0] * 1536

def process_page(page: Dict[str, Any], openai_client: OpenAI) -> List[Dict[str, Any]]:
    """Process a single page: split into chunks and generate embeddings."""
    url = page['url']
    markdown = page.get('markdown', '')
    
    if not markdown or markdown.strip() == "":
        print(f"Skipping {url} - no markdown content")
        return []
    
    print(f"Processing {url}")
    chunks = split_text_into_chunks(markdown)
    
    result = []
    for i, chunk in enumerate(chunks):
        # Generate embedding for the chunk
        embedding = generate_embedding(openai_client, chunk)
        
        # Create a record for the chunk
        chunk_record = {
            'url': url,
            'chunk_idx': i,
            'content': chunk,
            'embedding': embedding
        }
        
        result.append(chunk_record)
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    return result

def upsert_chunks(supabase_client: Client, chunks: List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Upsert chunks into the pages_chunks table.
    Returns a dictionary with success and error counts.
    """
    if not chunks:
        return {"success": 0, "error": 0}
    
    success_count = 0
    error_count = 0
    
    try:
        # Upsert data (insert if not exists, update if exists)
        result = supabase_client.table('pages_chunks').upsert(chunks).execute()
        
        # Check if the operation was successful
        if hasattr(result, 'data'):
            success_count = len(chunks)
            print(f"Successfully upserted {success_count} chunks")
        else:
            error_count = len(chunks)
            print(f"Error upserting {error_count} chunks")
                
    except Exception as e:
        error_count = len(chunks)
        print(f"Error upserting chunks: {e}")
    
    return {
        "success": success_count,
        "error": error_count
    }

def main():
    """Main function to orchestrate the embedding generation process."""
    start_time = time.time()
    
    # Check for required environment variables
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables must be set.")
        exit(1)
    
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY environment variable must be set.")
        exit(1)
    
    # Connect to services
    supabase_client = connect_to_supabase()
    openai_client = connect_to_openai()
    
    # Create the pages_chunks table if it doesn't exist
    create_pages_chunks_table_if_not_exists(supabase_client)
    
    # Fetch pages from Supabase
    print("Fetching pages from Supabase...")
    pages = fetch_pages(supabase_client)
    
    if not pages:
        print("No pages found in Supabase. Exiting.")
        return
    
    print(f"Found {len(pages)} pages in Supabase.")
    
    # Process pages in batches
    total_pages = len(pages)
    total_chunks_success = 0
    total_chunks_error = 0
    
    for i in range(0, total_pages, BATCH_SIZE):
        batch = pages[i:i+BATCH_SIZE]
        batch_size = len(batch)
        
        print(f"\nProcessing batch {i//BATCH_SIZE + 1} ({i+1}-{min(i+batch_size, total_pages)} of {total_pages} pages)")
        
        # Process each page in the batch
        all_chunks = []
        for page in batch:
            page_chunks = process_page(page, openai_client)
            all_chunks.extend(page_chunks)
        
        # Upsert chunks to Supabase
        if all_chunks:
            results = upsert_chunks(supabase_client, all_chunks)
            total_chunks_success += results["success"]
            total_chunks_error += results["error"]
        
        # Small delay between batches
        if i + BATCH_SIZE < total_pages:
            print(f"Waiting before processing next batch...")
            time.sleep(1)
    
    # Print summary
    elapsed_time = time.time() - start_time
    print("\n" + "="*50)
    print("EMBEDDING GENERATION SUMMARY")
    print("="*50)
    print(f"Total pages processed: {total_pages}")
    print(f"Total chunks generated: {total_chunks_success + total_chunks_error}")
    print(f"Successfully upserted chunks: {total_chunks_success}")
    print(f"Failed to upsert chunks: {total_chunks_error}")
    print(f"Time elapsed: {elapsed_time:.2f} seconds")
    print("="*50)
    
    if total_chunks_error > 0:
        print("\nWarning: Some chunks failed to upsert. Check the logs above for details.")
    else:
        print("\nSuccess: All chunks were generated and upserted successfully!")

if __name__ == "__main__":
    main()
