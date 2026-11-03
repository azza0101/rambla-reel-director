"""Validation of one-shot media exclusions for Resolve export."""
from fastapi import HTTPException


def ignored_for_export(raw: str) -> set[str]:
    if len(raw) > 12000:
        raise HTTPException(status_code=422, detail="Troppi asset ignorati")
    values = {part.strip() for part in raw.split(",") if part.strip()}
    if len(values) > 200 or any(
        len(value) > 1000 or any(ord(char) < 32 for char in value)
        for value in values
    ):
        raise HTTPException(status_code=422, detail="Identificatori coperture non validi")
    return values
