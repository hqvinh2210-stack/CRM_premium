# Orchestrator — Linear Webhook (Phần 3)

FastAPI backend nhận sự kiện webhook từ Linear (Issue Created, …).

## Cài đặt

```powershell
cd C:\Users\admin\Downloads\CRM\orchestrator
uv sync
```

## Chạy local

```powershell
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

- Health: http://127.0.0.1:8000/
- Webhook: `POST` http://127.0.0.1:8000/linear
- Docs: http://127.0.0.1:8000/docs

## Expose bằng ngrok

Terminal 1 — FastAPI:

```powershell
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — ngrok:

```powershell
ngrok http 8000
```

Copy URL public, ví dụ:

```text
https://xxxxx.ngrok-free.app
```

Webhook URL dán vào Linear:

```text
https://xxxxx.ngrok-free.app/linear
```

## Cấu hình Linear Webhook

1. Linear → **Settings** → **API** → **Webhooks** (hoặc Workspace Settings → Webhooks)
2. **New webhook**
3. URL: `https://<ngrok-host>/linear`
4. Bật event **Issue** (created / updated — tùy nhu cầu)
5. Save

## Kiểm tra

1. Tạo issue mới trên Linear
2. Xem terminal FastAPI: payload `dict` được `print`
3. Response `{"ok": true}`

## Luồng

```text
Issue Created (Linear)
        ↓
     Webhook
        ↓
   FastAPI /linear
        ↓
     print(data)
```
