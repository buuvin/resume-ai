from io import BytesIO
from pathlib import Path

import pdfplumber
from docx import Document
from fastapi import UploadFile

SUPPORTED_EXTENSIONS = {".txt", ".md", ".rtf", ".pdf", ".docx"}


async def extract_upload_text(upload: UploadFile) -> str:
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Use .txt, .md, .rtf, .pdf, or .docx."
        )

    content = await upload.read()
    if not content:
        return ""

    if extension in {".txt", ".md", ".rtf"}:
        return content.decode("utf-8", errors="replace").strip()

    if extension == ".pdf":
        with pdfplumber.open(BytesIO(content)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()

    document = Document(BytesIO(content))
    return "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
