#!/opt/homebrew/bin/python3
"""
Test Vector Search with Supabase

This script demonstrates how to use the match_chunks function to perform
vector similarity search against the embeddings in the pages_chunks table.
"""

import os
import json
import requests
from supabase import create_client

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

def create_embedding(text):
    """Create an embedding for a single text using OpenAI's API."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    
    data = {
        "input": text,
        "model": EMBED_MODEL
    }
    
    api_url = f"{OPENAI_API_BASE}/embeddings"
    
    try:
        print(f"Generating embedding for query: '{text}'")
        response = requests.post(
            api_url,
            headers=headers,
            json=data
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["data"][0]["embedding"]
        else:
            print(f"Error: API returned status {response.status_code}")
            print(response.text)
            return None
    except Exception as e:
        print(f"Error creating embedding: {e}")
        return None

def search_similar_chunks(query, top_k=5):
    """
    Search for chunks similar to the query using the match_chunks function.
    
    Args:
        query (str): The search query
        top_k (int): Number of results to return
        
    Returns:
        list: List of matching chunks with their scores
    """
    # Connect to Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # Generate embedding for the query
    query_embedding = create_embedding(query)
    
    if not query_embedding:
        print("Failed to generate embedding for the query.")
        return []
    
    # Call the match_chunks function
    try:
        print(f"Searching for top {top_k} matches...")
        response = supabase.rpc(
            'match_chunks',
            {
                'q': query_embedding,
                'k': top_k
            }
        ).execute()
        
        if hasattr(response, 'data'):
            return response.data
        else:
            print("Error: Response has no data attribute")
            return []
    except Exception as e:
        print(f"Error searching for similar chunks: {e}")
        return []

def main():
    """Main function to test vector search."""
    print("=" * 50)
    print("VECTOR SIMILARITY SEARCH TEST")
    print("=" * 50)
    
    # Get user query
    query = input("Enter your search query: ")
    
    if not query:
        print("No query provided. Exiting.")
        return
    
    # Search for similar chunks
    results = search_similar_chunks(query)
    
    if not results:
        print("No results found.")
        return
    
    # Display results
    print("\n" + "=" * 50)
    print(f"TOP {len(results)} RESULTS FOR: '{query}'")
    print("=" * 50)
    
    for i, result in enumerate(results):
        print(f"\n[{i+1}] Score: {result['score']:.4f}")
        print(f"URL: {result['url']}")
        print("-" * 40)
        print(result['content'][:300] + "..." if len(result['content']) > 300 else result['content'])
        print("-" * 40)
    
    print("\nSearch complete!")

if __name__ == "__main__":
    main()
