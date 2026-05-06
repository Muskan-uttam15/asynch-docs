import json
import os
from collections.abc import Generator

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import Base, engine, get_db
from app.models import Document, JobStatus
from app.redis_client import progress_channel, redis_client
from app.schemas import DocumentOut, UpdateDocumentPayload
from app.services import export_as_csv, export_as_json, list_documents, save_upload_file
from app.tasks import process_document

os.makedirs(settings.upload_dir, exist_ok=True)
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Async Document Processing API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/documents/upload", response_model=list[DocumentOut])
def upload_documents(files: list[UploadFile] = File(...), db: Session = Depends(get_db)):
    created: list[Document] = []
    for file in files:
        storage_path, size = save_upload_file(settings.upload_dir, file)
        doc = Document(
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            size_bytes=size,
            storage_path=storage_path,
            status=JobStatus.QUEUED,
            progress=0,
            stage="job_queued",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        created.append(doc)
        process_document.delay(doc.id)
    return created


@app.get("/documents", response_model=list[DocumentOut])
def get_documents(
    search: str | None = None,
    status: JobStatus | None = None,
    sort_by: str = Query(default="created_at"),
    order: str = Query(default="desc"),
    db: Session = Depends(get_db),
):
    return list_documents(db, search, status, sort_by, order)


@app.get("/documents/{document_id}", response_model=DocumentOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@app.post("/documents/{document_id}/retry", response_model=DocumentOut)
def retry_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != JobStatus.FAILED:
        raise HTTPException(status_code=400, detail="Only failed jobs can be retried")
    doc.status = JobStatus.QUEUED
    doc.progress = 0
    doc.stage = "job_queued"
    doc.error_message = None
    db.commit()
    db.refresh(doc)
    process_document.delay(doc.id)
    return doc


@app.put("/documents/{document_id}/review", response_model=DocumentOut)
def update_review(document_id: int, payload: UpdateDocumentPayload, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    doc.finalized_data = payload.data
    db.commit()
    db.refresh(doc)
    return doc


@app.post("/documents/{document_id}/finalize", response_model=DocumentOut)
def finalize_document(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Document must be completed first")
    doc.is_finalized = True
    db.commit()
    db.refresh(doc)
    return doc


@app.get("/documents/export/json")
def export_json(db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.is_finalized.is_(True))).all()
    return PlainTextResponse(export_as_json(docs), media_type="application/json")


@app.get("/documents/export/csv")
def export_csv(db: Session = Depends(get_db)):
    docs = db.scalars(select(Document).where(Document.is_finalized.is_(True))).all()
    return PlainTextResponse(export_as_csv(docs), media_type="text/csv")


@app.get("/documents/{document_id}/progress")
def stream_progress(document_id: int, db: Session = Depends(get_db)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    def event_stream() -> Generator[str, None, None]:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(progress_channel(document_id))
        try:
            initial = {
                "document_id": doc.id,
                "event": doc.stage,
                "progress": doc.progress,
                "status": doc.status.value,
                "message": doc.error_message,
            }
            yield f"data: {json.dumps(initial)}\n\n"
            for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                payload = message["data"]
                yield f"data: {payload}\n\n"
        finally:
            pubsub.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")
