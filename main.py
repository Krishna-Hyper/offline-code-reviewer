import json
import os
import httpx
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from pydantic import BaseModel

app = FastAPI(title="Offline Code Reviewer")
MODEL = "qwen3:4b"
OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_TAGS_URL = "http://localhost:11434/api/tags"

SYSTEM = SYSTEM = SYSTEM = """You are a strict, automated code reviewer. You MUST output ONLY the final markdown report. 
CRITICAL: Do NOT include any preamble, thinking process, steps, or meta-commentary. Start directly with "## Summary".

Use this exact format and rules:

## Summary
One or two sentences on what the code does.

## Bugs
Prefix every finding with a severity tag: [CRITICAL], [WARNING], or [INFO].
- [CRITICAL] use for bugs that crash, corrupt data, or cause security holes.
- [WARNING]  use for logic errors, edge cases, and likely mistakes.
- [INFO]     use for minor issues and style nits.
Write "None found" if clean. Include line numbers.

## Improvements
- Readability, naming, structure, performance. No severity tags needed here.

## Security
Prefix every finding with [CRITICAL], [WARNING], or [INFO].

## Complexity
Time and space complexity if it is an algorithm. Otherwise write "N/A".

EXAMPLE STRICT OUTPUT:
## Summary
A SQLite helper function.

## Bugs
- [CRITICAL] Line 8: SQL injection via f-string.

## Improvements
- Use parameterised queries.

## Security
- [CRITICAL] Line 2: Hardcoded database password.

## Complexity
N/A"""
FOCUS = {
    "general": "Do a general review.",
    "bugs": "Focus mainly on finding bugs and edge cases.",
    "security": "Focus mainly on security issues.",
    "performance": "Focus mainly on performance and complexity.",
}

class ReviewRequest(BaseModel):
    code: str
    language: str = "auto-detect"
    focus: str = "general"


@app.post("/review")
async def review(req: ReviewRequest):
    user_msg = (
        f"{FOCUS.get(req.focus, FOCUS['general'])}\n"
        f"Language: {req.language}\n\n```\n{req.code[:6000]}\n```\n\n"
        "CRITICAL COMMAND: Do not write a single word of preamble, thinking, or explanation. Start your response exactly with:\n## Summary"
    )
    payload = {
        "model": MODEL,
        "stream": True,
        "think": False,
        "options": {
            "temperature": 0.4, 
            "num_ctx": 4096,
            "num_predict": 800
        },
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ],
    }

    async def generate():
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", OLLAMA_URL, json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield json.loads(line).get("message", {}).get("content", "")
        except httpx.ConnectError:
            yield "Could not reach Ollama. Is it running? Try: ollama serve"

    return StreamingResponse(generate(), media_type="text/plain")

@app.post("/fix")
async def fix_code(req: ReviewRequest):
    lang_tag = req.language.lower() if req.language != "auto-detect" else ""
    user_msg = (
        f"Language: {req.language}\n\n```\n{req.code[:6000]}\n```\n\n"
        "Fix all bugs, security flaws, and performance issues. "
        "Output ONLY the corrected code inside markdown backticks. Never write thoughts, steps, or explanations."
    )
    
    # We supply the opening ``` to force generation to start directly on the code!
    initial_code_start = f"```{lang_tag}\n"

    payload = {
        "model": MODEL,
        "stream": True,
        "think": False,
        "options": {
            "temperature": 0.1, 
            "num_ctx": 4096,
            "num_predict": 2000
        },
        "messages": [
            {
                "role": "system",
                "content": "You are a strict security engineer. Output ONLY the fixed code inside backticks. You MUST fix SQL injections using parameterized queries. You MUST replace hardcoded passwords and secrets with environment variable lookups (e.g., os.getenv). Fix all syntax errors. Do not explain anything."
            },
            {"role": "user", "content": user_msg},
            {"role": "assistant", "content": initial_code_start}
        ],
    }

    async def generate():
        # Yield the starting tag first so the stream starts clean
        yield initial_code_start
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", OLLAMA_URL, json=payload) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            yield json.loads(line).get("message", {}).get("content", "")
        except httpx.ConnectError:
            yield "\nCould not reach Ollama. Is it running?"

    return StreamingResponse(generate(), media_type="text/plain")


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(OLLAMA_TAGS_URL)
            tags = r.json()
        names = [m["name"] for m in tags.get("models", [])]
        model_installed = any(n == MODEL or n.startswith(MODEL + ":") for n in names)
        return {"ollama_running": True, "model": MODEL, "model_installed": model_installed}
    except Exception:
        return {"ollama_running": False, "model": MODEL, "model_installed": False}

@app.get("/", response_class=HTMLResponse)
async def home():
    if not os.path.exists("index.html"):
        return "<h1>Offline Code Reviewer</h1><p>Frontend coming soon.</p>"
    with open("index.html", encoding="utf-8") as f:
        return f.read()