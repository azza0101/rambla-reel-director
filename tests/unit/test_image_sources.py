import httpx
import pytest

from backend.app.image_sources import PexelsPhotoSource, WikimediaImageSource
from backend.app.online_assets import ProviderError


@pytest.mark.asyncio
async def test_wikimedia_source_normalizes_public_thumbnail():
    async def handler(request):
        return httpx.Response(200, json={"query": {"pages": {"1": {
            "title": "File:Elephant.jpg", "imageinfo": [{
                "url": "https://upload.wikimedia.org/full.jpg",
                "thumburl": "https://upload.wikimedia.org/thumb.jpg",
                "width": 1200, "height": 800,
                "extmetadata": {"LicenseShortName": {"value": "CC BY-SA"}},
            }],
        }}}})
    rows = await WikimediaImageSource(transport=httpx.MockTransport(handler)).search("elephant", limit=2)
    assert rows[0].kind == "image"
    assert rows[0].provider == "wikimedia"
    assert rows[0].source_page.startswith("https://commons.wikimedia.org/")
    assert rows[0].thumbnail_url.startswith("https://")


@pytest.mark.asyncio
async def test_pexels_photo_source_normalizes_and_hides_missing_key():
    async def handler(request):
        return httpx.Response(200, json={"photos": [{
            "id": 7, "url": "https://www.pexels.com/photo/7/", "alt": "Sea",
            "width": 800, "height": 1200,
            "src": {"medium": "https://images.pexels.com/m.jpg", "original": "https://images.pexels.com/o.jpg"},
        }]})
    rows = await PexelsPhotoSource("secret", transport=httpx.MockTransport(handler)).search("sea", limit=2)
    assert rows[0].provider == "pexels"
    assert rows[0].source_page.startswith("https://www.pexels.com/photo/")
    assert rows[0].rights_state == "provider_stock_terms"
    with pytest.raises(ProviderError, match="not configured"):
        await PexelsPhotoSource(None).search("sea", limit=1)
