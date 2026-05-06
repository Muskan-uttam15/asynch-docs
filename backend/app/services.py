import csv
import io
import json
import os
from typing import Any

from fastapi import UploadFile
from sqlalchemy import Select, asc, desc, select
from sqlalchemy.orm import Session

from app.models import Document, JobStatus


def save_upload_file(upload_dir: str, file: UploadFile) -> tuple[str, int]:
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    return file_path, len(content)


def list_documents(
    db: Session,
    search: str | None,
    status: JobStatus | None,
    sort_by: str,
    order: str,
) -> list[Document]:
    query: Select[tuple[Document]] = select(Document)
    if search:
        query = query.where(Document.filename.ilike(f"%{search}%"))
    if status:
        query = query.where(Document.status == status)

    sort_column = {
        "created_at": Document.created_at,
        "filename": Document.filename,
        "status": Document.status,
        "updated_at": Document.updated_at,
    }.get(sort_by, Document.created_at)
    sort_order = desc(sort_column) if order.lower() == "desc" else asc(sort_column)
    query = query.order_by(sort_order)
    return db.scalars(query).all()


def export_as_json(docs: list[Document]) -> str:
    payload = [
        {
            "id": doc.id,
            "filename": doc.filename,
            "status": doc.status.value,
            "finalized_data": doc.finalized_data,
            "updated_at": doc.updated_at.isoformat(),
        }
        for doc in docs
    ]
    return json.dumps(payload, indent=2)


def export_as_csv(docs: list[Document]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "filename", "status", "title", "category", "summary", "keywords"])
    for doc in docs:
        data: dict[str, Any] = doc.finalized_data or {}
        writer.writerow(
            [
                doc.id,
                doc.filename,
                doc.status.value,
                data.get("title", ""),
                data.get("category", ""),
                data.get("summary", ""),
                "|".join(data.get("keywords", [])),
            ]
        )
    return output.getvalue()
