import os
import shutil

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
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


@app.get("/")
def health():
    return {"status": "ok", "message": "server running"}


@app.post("/upload")
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
        "message": "file uploaded and indexed: " + file.filename
    }


class AskRequest(BaseModel):
    question: str


@app.post("/ask")
def ask_question(req: AskRequest):
    try:
        answer = ask(req.question)
        return {"status": "ok", "question": req.question, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
