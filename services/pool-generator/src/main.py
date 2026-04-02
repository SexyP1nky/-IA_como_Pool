"""Pool Generator service entrypoint."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(
    title="Pool Generator API",
    description="Serviço responsável por gerar e manter o pool de desafios",
    version="1.0.0",
)


@app.get("/health")
async def health() -> JSONResponse:
    """Health check endpoint for container and CI validation."""
    return JSONResponse(content={"status": "healthy"})
