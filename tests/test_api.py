"""Focused API tests for safe document registration and YouTube ingestion."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    from config import settings
    import api.service as service

    monkeypatch.setattr(settings, "documents_dir", str(tmp_path))
    monkeypatch.setattr(settings, "upload_max_bytes", 1_000_000)
    return TestClient(service.app)


def test_youtube_url_is_registered(api_client, tmp_path):
    response = api_client.post(
        "/documents/youtube",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 200
    assert response.json()["filename"] == "youtube_dQw4w9WgXcQ.yt"
    assert (tmp_path / "youtube_dQw4w9WgXcQ.yt").read_text() == \
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_duplicate_youtube_is_rejected(api_client):
    payload = {"url": "https://youtu.be/dQw4w9WgXcQ"}
    assert api_client.post("/documents/youtube", json=payload).status_code == 200
    assert api_client.post("/documents/youtube", json=payload).status_code == 409


def test_file_upload_does_not_overwrite_existing_file(api_client, tmp_path):
    existing = tmp_path / "notes.pdf"
    existing.write_bytes(b"original")

    response = api_client.post(
        "/documents",
        files={"files": ("notes.pdf", b"replacement", "application/pdf")},
    )
    assert response.status_code == 200
    assert response.json()["saved"] == []
    assert response.json()["rejected"][0]["filename"] == "notes.pdf"
    assert existing.read_bytes() == b"original"
