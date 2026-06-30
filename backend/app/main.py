import os
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.document import load_and_split, store_to_faiss
from app.qa import ask

app = FastAPI(title="AI KB QA System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")


@app.get("/api/health")
def health():
    return {"status": "ok", "message": "server running"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        chunks = load_and_split(file_path)
        store_to_faiss(chunks)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "ok",
        "filename": file.filename,
        "size": os.path.getsize(file_path),
        "chunks": len(chunks),
        "message": "file uploaded and indexed: " + file.filename,
    }


class AskRequest(BaseModel):
    question: str


@app.post("/api/ask")
def ask_question(req: AskRequest):
    try:
        answer = ask(req.question)
        return {"status": "ok", "question": req.question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Serve frontend - catch-all must be last
@app.get("/{path:path}")
def serve_frontend(path: str):
    file_path = os.path.join(FRONTEND_DIR, path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))