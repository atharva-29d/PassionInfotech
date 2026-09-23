import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from graph_routes import router as graph_router
import uvicorn

app = FastAPI(title="Threat Hunting Graph API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(graph_router, prefix="/api/graph", tags=["graph"])

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
