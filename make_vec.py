# save as make_vec.py
import os, json
from openai import OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
vec = client.embeddings.create(
        model="text-embedding-3-small",
        input="student life at Hotchkiss"
      ).data[0].embedding
print(json.dumps(vec))