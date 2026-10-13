import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional

import anthropic
import httpx
import yaml
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(
    level=os.getenv("ROUTER_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("router")

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
COMPLEXITY_TOKEN_THRESHOLD = int(os.getenv("COMPLEXITY_TOKEN_THRESHOLD", "800"))

# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class AgentConfig:
    def __init__(self, data: dict):
        self.id: str = data["id"]
        self.name: str = data["name"]
        self.description: str = data.get("description", "")
        self.local_model: str = data["local_model"]
        self.cloud_model: str = data["cloud_model"]
        self.complexity_keywords: list[str] = data.get("complexity_keywords", [])
        self.system_prompt: str = data.get("system_prompt", "").strip()


def load_agents(path: str = "/app/agents.yaml") -> dict[str, AgentConfig]:
    p = Path(path)
    if not p.exists():
        p = Path(__file__).parent / "agents.yaml"
    with open(p) as f:
        data = yaml.safe_load(f)
    return {a["id"]: AgentConfig(a) for a in data["agents"]}


AGENTS: dict[str, AgentConfig] = {}


# ---------------------------------------------------------------------------
# Pydantic models (OpenAI-compatible)
# ---------------------------------------------------------------------------

class Message(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None


# ---------------------------------------------------------------------------
# Complexity classifier
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return len(text) // 4


def classify_complexity(request: ChatCompletionRequest, agent: AgentConfig) -> str:
    """Return 'local' or 'cloud' based on message complexity."""
    model_lower = request.model.lower()
    if model_lower.startswith("ollama/"):
        return "local"
    if model_lower.startswith("cloud/"):
        return "cloud"

    # Collect all message text for analysis
    full_text = " ".join(m.content for m in request.messages).lower()

    # Keyword match forces cloud
    for kw in agent.complexity_keywords:
        if kw.lower() in full_text:
            log.info("keyword match '%s' → cloud", kw)
            return "cloud"

    # Token threshold check on the last user message
    last_user = next(
        (m.content for m in reversed(request.messages) if m.role == "user"), ""
    )
    tokens = estimate_tokens(last_user)
    if tokens > COMPLEXITY_TOKEN_THRESHOLD:
        log.info("token count %d > threshold %d → cloud", tokens, COMPLEXITY_TOKEN_THRESHOLD)
        return "cloud"

    return "local"


# ---------------------------------------------------------------------------
# System prompt injection
# ---------------------------------------------------------------------------

def inject_system_prompt(messages: list[Message], system_prompt: str) -> list[Message]:
    if not system_prompt:
        return messages
    if messages and messages[0].role == "system":
        # Prepend agent prompt to any existing system message
        messages[0] = Message(
            role="system",
            content=f"{system_prompt}\n\n---\n\n{messages[0].content}",
        )
        return messages
    return [Message(role="system", content=system_prompt)] + messages


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def make_chunk(content: str, model: str, finish_reason: Optional[str] = None) -> str:
    chunk = {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {"content": content} if content else {},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def make_completion(content: str, model: str, prompt_tokens: int) -> dict:
    completion_tokens = estimate_tokens(content)
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:8]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


# ---------------------------------------------------------------------------
# Ollama provider
# ---------------------------------------------------------------------------

async def stream_ollama(
    model: str, messages: list[Message], temperature: Optional[float], max_tokens: Optional[int]
) -> AsyncIterator[str]:
    payload: dict = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": True,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    if max_tokens is not None:
        payload.setdefault("options", {})["num_predict"] = max_tokens

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", f"{OLLAMA_BASE_URL}/api/chat", json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise HTTPException(status_code=resp.status_code, detail=body.decode())
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = data.get("message", {}).get("content", "")
                done = data.get("done", False)
                if content:
                    yield make_chunk(content, model)
                if done:
                    yield make_chunk("", model, finish_reason="stop")
                    yield "data: [DONE]\n\n"
                    return


async def complete_ollama(
    model: str, messages: list[Message], temperature: Optional[float], max_tokens: Optional[int]
) -> dict:
    payload: dict = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False,
    }
    if temperature is not None:
        payload["options"] = {"temperature": temperature}
    if max_tokens is not None:
        payload.setdefault("options", {})["num_predict"] = max_tokens

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        data = resp.json()
        content = data.get("message", {}).get("content", "")
        prompt_tokens = estimate_tokens(" ".join(m.content for m in messages))
        return make_completion(content, model, prompt_tokens)


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

async def stream_anthropic(
    model: str, messages: list[Message], temperature: Optional[float], max_tokens: Optional[int]
) -> AsyncIterator[str]:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    system_text = ""
    filtered: list[dict] = []
    for m in messages:
        if m.role == "system":
            system_text = m.content
        else:
            filtered.append({"role": m.role, "content": m.content})

    kwargs: dict = {
        "model": model,
        "messages": filtered,
        "max_tokens": max_tokens or 4096,
    }
    if system_text:
        kwargs["system"] = system_text
    if temperature is not None:
        kwargs["temperature"] = temperature

    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield make_chunk(text, model)
        yield make_chunk("", model, finish_reason="stop")
        yield "data: [DONE]\n\n"


async def complete_anthropic(
    model: str, messages: list[Message], temperature: Optional[float], max_tokens: Optional[int]
) -> dict:
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not configured")

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

    system_text = ""
    filtered: list[dict] = []
    for m in messages:
        if m.role == "system":
            system_text = m.content
        else:
            filtered.append({"role": m.role, "content": m.content})

    kwargs: dict = {
        "model": model,
        "messages": filtered,
        "max_tokens": max_tokens or 4096,
    }
    if system_text:
        kwargs["system"] = system_text
    if temperature is not None:
        kwargs["temperature"] = temperature

    response = await client.messages.create(**kwargs)
    content = response.content[0].text if response.content else ""
    prompt_tokens = response.usage.input_tokens
    return make_completion(content, model, prompt_tokens)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Agent Router", version="1.0.0")


@app.on_event("startup")
async def startup():
    global AGENTS
    AGENTS = load_agents()
    log.info("Loaded %d agents: %s", len(AGENTS), list(AGENTS.keys()))


@app.get("/health")
async def health():
    return {"status": "ok", "agents": list(AGENTS.keys())}


@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": agent_id,
                "object": "model",
                "created": 0,
                "owned_by": "local-router",
                "description": agent.description,
            }
            for agent_id, agent in AGENTS.items()
        ],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    model_id = request.model.removeprefix("ollama/").removeprefix("cloud/")

    agent = AGENTS.get(model_id)
    if agent is None:
        # Pass through unknown models directly to Ollama
        log.warning("Unknown agent '%s', passing through to Ollama", model_id)
        if request.stream:
            return StreamingResponse(
                stream_ollama(model_id, request.messages, request.temperature, request.max_tokens),
                media_type="text/event-stream",
            )
        return await complete_ollama(model_id, request.messages, request.temperature, request.max_tokens)

    route = classify_complexity(request, agent)
    messages = inject_system_prompt(list(request.messages), agent.system_prompt)

    if route == "cloud":
        target_model = agent.cloud_model
        log.info("agent=%s route=cloud model=%s", agent.id, target_model)
        if request.stream:
            return StreamingResponse(
                stream_anthropic(target_model, messages, request.temperature, request.max_tokens),
                media_type="text/event-stream",
            )
        return await complete_anthropic(target_model, messages, request.temperature, request.max_tokens)
    else:
        target_model = agent.local_model
        log.info("agent=%s route=local model=%s", agent.id, target_model)
        if request.stream:
            return StreamingResponse(
                stream_ollama(target_model, messages, request.temperature, request.max_tokens),
                media_type="text/event-stream",
            )
        return await complete_ollama(target_model, messages, request.temperature, request.max_tokens)
