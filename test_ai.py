import os
import requests
from dotenv import load_dotenv
load_dotenv()

# Test OpenRouter
print("=" * 50)
print("Testing OpenRouter...")
print("=" * 50)
try:
    res = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": "Bearer " + os.getenv("OPENROUTER_API_KEY"),
            "Content-Type": "application/json",
            "HTTP-Referer": "https://osceai.onrender.com",
            "X-Title": "OsceAI"
        },
        json={
            "model": "mistralai/mistral-small-3.1-24b-instruct:free",
            "messages": [{"role": "user", "content": "Say hello in one sentence"}],
            "max_tokens": 30
        },
        timeout=30
    )
    data = res.json()
    if "choices" in data:
        print("SUCCESS:", data["choices"][0]["message"]["content"])
    else:
        print("FAILED:", data)
except Exception as e:
    print("ERROR:", e)

# Test Gemini
print()
print("=" * 50)
print("Testing Gemini...")
print("=" * 50)
try:
    res = requests.post(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=" + os.getenv("GEMINI_API_KEY"),
        headers={"Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": "Say hello in one sentence"}]}],
            "generationConfig": {"maxOutputTokens": 30}
        },
        timeout=30
    )
    data = res.json()
    if "candidates" in data:
        print("SUCCESS:", data["candidates"][0]["content"]["parts"][0]["text"])
    else:
        print("FAILED:", data)
except Exception as e:
    print("ERROR:", e)

# Test Cohere
print()
print("=" * 50)
print("Testing Cohere...")
print("=" * 50)
try:
    res = requests.post(
        "https://api.cohere.com/v1/chat",
        headers={
            "Authorization": "Bearer " + os.getenv("COHERE_API_KEY"),
            "Content-Type": "application/json"
        },
        json={
            "model": "command-r-plus-08-2024",
            "message": "Say hello in one sentence",
            "max_tokens": 30
        },
        timeout=30
    )
    data = res.json()
    if "text" in data:
        print("SUCCESS:", data["text"])
    else:
        print("FAILED:", data)
except Exception as e:
    print("ERROR:", e)

print()
print("=" * 50)
print("Test complete!")
print("=" * 50)