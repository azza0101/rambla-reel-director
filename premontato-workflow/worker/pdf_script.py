"""Local extraction of screenplay text from PDF without any cloud processing."""
from pathlib import Path


def extract_pdf_text(path):
    from pypdf import PdfReader

    file_path = Path(path)
    if file_path.suffix.casefold() != ".pdf":
        raise ValueError("Il file selezionato non è un PDF")
    reader = PdfReader(str(file_path))
    if reader.is_encrypted:
        raise ValueError("Il PDF è protetto da password")
    pages = [page.extract_text(extraction_mode="layout") or "" for page in reader.pages]
    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError("Il PDF non contiene testo estraibile; serve OCR per questo documento")
    return text
