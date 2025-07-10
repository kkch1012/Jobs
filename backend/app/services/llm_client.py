from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY"),
)

def get_openrouter_completion(
        messages, 
        model="google/gemma-3n-e2b-it:free", 
        site_url=None, 
        site_title=None):
    extra_headers = {}
    if site_url:
        extra_headers["HTTP-Referer"] = site_url
    if site_title:
        extra_headers["X-Title"] = site_title

    completion = client.chat.completions.create(
        extra_headers=extra_headers,
        extra_body={},
        model=model,
        messages=messages,
    )
    return completion.choices[0].message.content
