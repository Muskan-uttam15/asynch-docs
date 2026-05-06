import os
import time

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models import Document, JobStatus
from app.redis_client import publish_progress


def emit(
    document: Document,
    event: str,
    progress: int,
    status: JobStatus,
    message: str | None = None,
) -> None:
    payload = {
        "document_id": document.id,
        "event": event,
        "progress": progress,
        "status": status.value,
        "message": message,
    }
    publish_progress(document.id, payload)


@celery_app.task(name="process_document")
def process_document(document_id: int) -> None:
    db = SessionLocal()
    try:
        doc = db.get(Document, document_id)
        if not doc:
            return

        doc.status = JobStatus.PROCESSING
        doc.progress = 5
        doc.stage = "job_started"
        doc.error_message = None
        doc.attempts += 1
        db.commit()
        emit(doc, "job_started", 5, JobStatus.PROCESSING)
        time.sleep(1)

        doc.stage = "document_parsing_started"
        doc.progress = 20
        db.commit()
        emit(doc, "document_parsing_started", 20, JobStatus.PROCESSING)
        time.sleep(1)

        doc.stage = "document_parsing_completed"
        doc.progress = 40
        db.commit()
        emit(doc, "document_parsing_completed", 40, JobStatus.PROCESSING)
        time.sleep(1)

        doc.stage = "field_extraction_started"
        doc.progress = 60
        db.commit()
        emit(doc, "field_extraction_started", 60, JobStatus.PROCESSING)
        time.sleep(1)

        filename = os.path.basename(doc.filename)
        extracted = {
            "title": filename.rsplit(".", 1)[0].replace("_", " ").title(),
            "category": "General",
            "summary": f"Auto-generated summary for {filename}",
            "keywords": ["document", "async", "processed"],
            "metadata": {
                "filename": doc.filename,
                "file_type": doc.content_type,
                "size_bytes": doc.size_bytes,
            },
            "status": "review_pending",
        }

        doc.stage = "field_extraction_completed"
        doc.progress = 85
        doc.extracted_data = extracted
        doc.finalized_data = extracted
        db.commit()
        emit(doc, "field_extraction_completed", 85, JobStatus.PROCESSING)
        time.sleep(1)

        doc.stage = "job_completed"
        doc.progress = 100
        doc.status = JobStatus.COMPLETED
        db.commit()
        emit(doc, "job_completed", 100, JobStatus.COMPLETED)
    except Exception as exc:
        db.rollback()
        doc = db.get(Document, document_id)
        if doc:
            doc.status = JobStatus.FAILED
            doc.stage = "job_failed"
            doc.error_message = str(exc)
            db.commit()
            emit(doc, "job_failed", doc.progress, JobStatus.FAILED, str(exc))
    finally:
        db.close()
