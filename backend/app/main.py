from fastapi import FastAPI

from app.api.v1.router import router as auth_router
from app.api.v1.endpoints.document_router import router as document_router
from app.api.v1.endpoints.retrieval_router import router as retrieval_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Enterprise AI Platform",
    version="1.0.0",
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth_router, prefix="/api/v1")
app.include_router(document_router, prefix="/api/v1")
app.include_router(retrieval_router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "status": "running",
        "service": "Enterprise AI Platform",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}