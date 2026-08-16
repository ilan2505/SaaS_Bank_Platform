from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import batches, records

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Financial Records Import API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(batches.router)
app.include_router(records.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
