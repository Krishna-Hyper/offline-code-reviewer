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

SYSTEM = """/no_think
You are a senior code reviewer. Review the code the user gives you.
Respond in exactly this markdown format:

## Summary
One or two sentences on what the code does.

## Bugs
- Real bugs or crashes (with line references). Write "None found" if clean.

## Improvements
- Readability, naming, structure, performance.

## Security
- Injection, unsafe input handling, secrets in code. Write "None found" if clean.

## Complexity
Time and space complexity if it is an algorithm.

Be concise. Do not rewrite the whole file."""

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
        f"Language: {req.language}\n\n```\n{req.code[:6000]}\n```"
    )
    payload = {
        "model": MODEL,
        "stream": True,
        "think": False,
        "options": {"temperature": 0.2, "num_ctx": 4096},
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