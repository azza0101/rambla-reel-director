from backend.app.social_media import classify_media_download_error


def test_youtube_unknown_error_is_not_fake_captcha():
    text=classify_media_download_error("ERROR: yt_dlp extractor encountered unexpected issue")
    assert "non è stato rilevato un CAPTCHA" in text


def test_youtube_format_unavailable_has_distinct_error():
    text=classify_media_download_error("ERROR: Requested format is not available")
    assert "Formato video non disponibile" in text
    assert "CAPTCHA" not in text


def test_youtube_auth_rejection_explains_browser_cookie_gap():
    text=classify_media_download_error("ERROR: Sign in to confirm your account")
    assert "cookie" in text.casefold()


def test_youtube_anti_bot_is_explicitly_detected():
    text=classify_media_download_error("ERROR: Sign in to confirm you're not a bot")
    assert "anti-bot" in text


def test_youtube_http_403_not_called_captcha():
    text=classify_media_download_error("ERROR: HTTP Error 403: Forbidden")
    assert "(403)" in text
    assert "CAPTCHA" not in text
