#!/usr/bin/env python3
import asyncio
import time
from contextlib import asynccontextmanager
from typing import List, Union

import torch
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import AutoModel, AutoTokenizer

MODEL_NAME = "Qwen/Qwen2.5-0.5B"
LAYER = 5
BATCH_SIZE = 512
MAX_LENGTH = 128
PORT = 8000

model = None
tokenizer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global model, tokenizer
    print(f"Loading {MODEL_NAME} (layer={LAYER}, pool=max) ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.pad_token = tokenizer.eos_token
    model = (
        AutoModel.from_pretrained(
            MODEL_NAME,
            output_hidden_states=True,
            torch_dtype=torch.float16,
        )
        .cuda()
        .eval()
    )
    try:
        model = torch.compile(model, mode="max-autotune")
        print("torch.compile enabled")
    except Exception as e:
        print(f"torch.compile skipped: {e}")
    print("Ready.")
    yield
    del model, tokenizer
    torch.cuda.empty_cache()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)

embed_lock = asyncio.Lock()


# ── schemas ───────────────────────────────────────────────────────────────────


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = MODEL_NAME
    encoding_format: str = "float"


class EmbeddingObject(BaseModel):
    object: str = "embedding"
    index: int
    embedding: List[float]


class UsageInfo(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingObject]
    model: str
    usage: UsageInfo


# ── embed ─────────────────────────────────────────────────────────────────────


def _embed(texts: List[str]) -> List[List[float]]:
    all_vecs = []
    for i in range(0, len(texts), BATCH_SIZE):
        chunk = texts[i : i + BATCH_SIZE]
        inputs = tokenizer(
            chunk,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_LENGTH,
        ).to("cuda")
        with torch.no_grad():
            outputs = model(**inputs)
        hidden = outputs.hidden_states[LAYER]  # (B, seq, hidden)
        mask = inputs["attention_mask"].unsqueeze(-1).float()
        masked = hidden * mask + (1 - mask) * (-1e9)  # mask padding to -inf
        pooled = masked.max(dim=1).values  # (B, hidden)
        all_vecs.extend(pooled.cpu().float().tolist())
    return all_vecs


# ── routes ────────────────────────────────────────────────────────────────────


@app.get("/health")
def health():
    return {"status": "ok", "layer": LAYER, "pool": "max"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "local",
            }
        ],
    }


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
async def create_embeddings(req: EmbeddingRequest):
    texts = [req.input] if isinstance(req.input, str) else req.input
    async with embed_lock:
        loop = asyncio.get_event_loop()
        vecs = await loop.run_in_executor(None, _embed, texts)
    token_count = sum(len(tokenizer.encode(t, add_special_tokens=False)) for t in texts)
    return EmbeddingResponse(
        data=[EmbeddingObject(index=i, embedding=v) for i, v in enumerate(vecs)],
        model=req.model,
        usage=UsageInfo(prompt_tokens=token_count, total_tokens=token_count),
    )


if __name__ == "__main__":
    uvicorn.run(
        "embedding_server:app", host="0.0.0.0", port=PORT, workers=1, log_level="info"
    )
