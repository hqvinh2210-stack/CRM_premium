from fastapi import FastAPI, Request

app = FastAPI(title="CRM Linear Orchestrator")


@app.get("/")
async def health():
    return {"status": "ok", "service": "orchestrator"}


@app.post("/linear")
async def webhook(data: dict):
    """Receive Linear webhook events (e.g. Issue Created)."""
    print("=" * 60)
    print("Linear webhook received")
    print("=" * 60)
    print(data)
    print("=" * 60)
    return {"ok": True}


@app.post("/linear/raw")
async def webhook_raw(request: Request):
    """Optional: dump raw body for debugging signature / payload shape."""
    body = await request.json()
    print("Linear raw webhook:", body)
    return {"ok": True}
