"""API route tests for the authenticated workspace upload contract."""

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


class FakeDB:
    def __init__(self):
        self.items = []
        self.commits = 0

    def add(self, item):
        self.items.append(item)

    def commit(self):
        self.commits += 1


class FakeUpload:
    def __init__(self, filename, content):
        self.filename = filename
        self.content = content

    async def read(self):
        return self.content


@pytest.fixture()
def api_context(tmp_path, monkeypatch):
    from api import service
    from config import settings

    monkeypatch.setattr(settings, "data_dir", str(tmp_path / "data"))
    monkeypatch.setattr(settings, "upload_max_bytes", 32)
    db = FakeDB()
    user = SimpleNamespace(id="audit-user")
    workspace = SimpleNamespace(id="audit-workspace")

    yield service, user, workspace, db, tmp_path


def run(coro):
    return asyncio.run(coro)


def test_anonymous_auth_dependency_requires_credentials():
    from auth.dependencies import current_user

    with pytest.raises(HTTPException) as error:
        current_user(None, FakeDB())
    assert error.value.status_code == 401


def test_youtube_url_is_registered(api_context):
    service, user, workspace, db, tmp_path = api_context
    response = service.add_youtube(
        service.YouTubeRequest(url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        user,
        workspace,
        db,
    )
    assert response["filename"] == "youtube_dQw4w9WgXcQ.yt"
    path = tmp_path / "workspaces" / "audit-workspace" / "documents" / "youtube_dQw4w9WgXcQ.yt"
    assert path.read_text() == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert db.commits == 1


def test_duplicate_youtube_is_rejected(api_context):
    service, user, workspace, db, _ = api_context
    request = service.YouTubeRequest(url="https://youtu.be/dQw4w9WgXcQ")
    assert service.add_youtube(request, user, workspace, db)["filename"]
    with pytest.raises(HTTPException) as error:
        service.add_youtube(request, user, workspace, db)
    assert error.value.status_code == 409


def test_upload_validation_accepts_valid_png_and_identifies_duplicates(api_context):
    service, _, _, _, tmp_path = api_context
    content = b"\x89PNG\r\n\x1a\nvalid"
    assert service._safe_name("diagram.png") == "diagram.png"
    assert service._content_type_error("diagram.png", content) is None
    destination = tmp_path / "diagram.png"
    destination.write_bytes(content)
    assert destination.exists()
    assert destination.read_bytes() == content


def test_upload_rejects_unsupported_corrupt_and_oversized_files(api_context):
    service, _, _, _, _ = api_context
    from config import settings

    with pytest.raises(HTTPException):
        service._safe_name("notes.txt")
    assert service._content_type_error("broken.pdf", b"not a pdf") is not None
    assert len(b"\x89PNG\r\n\x1a\n" + b"x" * 40) > settings.upload_max_bytes
