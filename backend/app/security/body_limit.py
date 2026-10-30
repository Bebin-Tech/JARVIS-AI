"""Bound even chunked bodies before JSON parsing; no trust in Content-Length."""

from starlette.responses import JSONResponse


class BodyLimitMiddleware:
    def __init__(self, app, limit=65536):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks = []
        limit = 2_000_000 if scope.get("path") == "/api/voice/transcribe" else self.limit
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > limit:
                response = JSONResponse({"detail": "Request too large"}, status_code=413)
                return await response(scope, receive, send)
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        await self.app(scope, replay, send)
