"""Safe, structured media download issues exposed to the curation UI."""
from urllib.parse import urlsplit


def _safe_source(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.port:
        return ""
    return parsed.geturl()


def download_issue(candidate, error: Exception) -> dict[str, str]:
    detail = str(error or "").casefold()
    if str(candidate.provider) in {"youtube", "youtube_shorts"} and "accesso" in detail and "captcha" not in detail:
        reason = "login_required"
        message = "Accedi a YouTube in Impostazioni e riprova il download."
    elif any(token in detail for token in ("verification required", "captcha", "login", "sign in", "not a bot")):
        reason = "verification_required"
        message = "Apri la fonte e completa login/CAPTCHA, poi riprova il download."
    elif any(token in detail for token in ("media format", "format unavailable", "could not supply")):
        reason = "format_unavailable"
        message = "Questo formato non è scaricabile automaticamente: la clip viene saltata."
    else:
        reason = "download_failed"
        message = "Download non riuscito: apri la fonte per controllarla; la clip viene saltata."
    return {
        "asset_id": str(candidate.asset_id),
        "beat_id": str(candidate.chunk_id),
        "provider": str(candidate.provider),
        "title": str(candidate.title),
        "source_page": _safe_source(candidate.source_page),
        "reason": reason,
        "message": message,
    }
