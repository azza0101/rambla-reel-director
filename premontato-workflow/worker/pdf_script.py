"""Local extraction of screenplay text from PDF without any cloud processing."""
from pathlib import Path


def extract_pdf_text(path, page_start=None, page_end=None):
    from pypdf import PdfReader

    file_path = Path(path)
    if file_path.suffix.casefold() != ".pdf":
        raise ValueError("Il file selezionato non è un PDF")
    reader = PdfReader(str(file_path))
    if reader.is_encrypted:
        raise ValueError("Il PDF è protetto da password")
    if page_start is None and page_end is None:
        selected = reader.pages
    else:
        if type(page_start) is not int or type(page_end) is not int or not 1 <= page_start <= page_end <= len(reader.pages):
            raise ValueError("Intervallo pagine fuori dal PDF")
        selected = reader.pages[page_start - 1:page_end]
    pages = [page.extract_text(extraction_mode="layout") or "" for page in selected]
    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError("Il PDF non contiene testo estraibile; serve OCR per questo documento")
    return text
