from io import BytesIO
from pathlib import Path
import zipfile

import pytest

from backend.app.resolve_title_templates import (
    TemplateValidationError,
    inspect_drfx,
    install_template,
    store_uploaded_drfx,
    template_library,
)


SUPPLIED_KURA = Path("backend/assets/resolve_titles/KURA_paper_title_v9.drfx")


def drfx_bytes(*entries: tuple[str, bytes]) -> bytes:
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, content in entries:
            archive.writestr(name, content)
    return stream.getvalue()


def valid_bytes(name: str = "My_Title") -> bytes:
    return drfx_bytes((f"Edit/Titles/{name}/{name}.setting", b"Tools = ordered() {}"))


def test_inspects_supplied_kura_package_with_stable_identity():
    first = inspect_drfx(SUPPLIED_KURA)
    second = inspect_drfx(SUPPLIED_KURA)

    assert first.resolve_name == "KURA_paper_title_v9"
    assert first.template_id == second.template_id
    assert first.template_id.startswith("sha256-")
    assert first.setting_path.endswith("KURA_paper_title_v9.setting")


@pytest.mark.parametrize(
    "content, message",
    [
        (b"not a zip", "valid DRFX"),
        (drfx_bytes(("../escape.setting", b"x")), "unsafe path"),
        (drfx_bytes(("README.txt", b"x")), "one Fusion Title"),
        (
            drfx_bytes(
                ("Edit/Titles/A/A.setting", b"x"),
                ("Edit/Titles/B/B.setting", b"x"),
            ),
            "one Fusion Title",
        ),
    ],
)
def test_rejects_invalid_packages(tmp_path, content, message):
    package = tmp_path / "bad.drfx"
    package.write_bytes(content)

    with pytest.raises(TemplateValidationError, match=message):
        inspect_drfx(package)


def test_store_upload_is_atomic_and_library_reports_missing_file(tmp_path):
    root = tmp_path / "library"
    stored = store_uploaded_drfx(BytesIO(valid_bytes()), "custom.drfx", root)

    assert stored.source_path.is_file()
    assert stored.resolve_name == "My_Title"
    assert template_library(root, tmp_path / "bundled")[0].template_id == stored.template_id

    stored.source_path.unlink()
    assert template_library(root, tmp_path / "bundled") == []


def test_store_rejects_upload_over_limit(tmp_path):
    with pytest.raises(TemplateValidationError, match="too large"):
        store_uploaded_drfx(BytesIO(valid_bytes()), "large.drfx", tmp_path, max_bytes=10)


def test_install_preserves_collision_and_reuses_matching_hash(tmp_path):
    root = tmp_path / "library"
    installed = tmp_path / "resolve"
    template = store_uploaded_drfx(BytesIO(valid_bytes()), "shared.drfx", root)
    collision = installed / "shared.drfx"
    collision.parent.mkdir(parents=True)
    collision.write_bytes(b"different")

    first = install_template(template, installed)
    second = install_template(template, installed)

    assert collision.read_bytes() == b"different"
    assert first.status == "restart_required"
    assert first.destination.name.startswith("shared-")
    assert second.status == "installed"
    assert second.destination == first.destination
    extracted = installed / "Edit" / "Titles" / "My_Title" / "My_Title.setting"
    assert extracted.read_bytes() == b"Tools = ordered() {}"


def test_install_status_requires_the_extracted_resolve_title(tmp_path):
    from backend.app.resolve_title_templates import template_install_status
    root = tmp_path / "library"
    installed = tmp_path / "resolve"
    template = store_uploaded_drfx(BytesIO(valid_bytes()), "shared.drfx", root)
    installed.mkdir()
    (installed / "shared.drfx").write_bytes(template.source_path.read_bytes())

    assert template_install_status(template, installed) == "not_installed"
    install_template(template, installed)
    assert template_install_status(template, installed) == "installed"
