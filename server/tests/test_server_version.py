"""Tests for server version resolution from version.json."""
import json

import server


def test_server_version_reads_plain_release_version(tmp_path, monkeypatch):
    (tmp_path / "version.json").write_text(json.dumps({"version": "v1.3.1", "commitSha": ""}))
    monkeypatch.setattr(server, "cwd", str(tmp_path))

    assert server._server_version() == "v1.3.1"


def test_server_version_appends_commit_sha_when_present(tmp_path, monkeypatch):
    (tmp_path / "version.json").write_text(
        json.dumps({"version": "v1.3.1", "commitSha": "3418b8b"})
    )
    monkeypatch.setattr(server, "cwd", str(tmp_path))

    assert server._server_version() == "v1.3.1+3418b8b"


def test_server_version_falls_back_to_dev_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "cwd", str(tmp_path))

    assert server._server_version() == "dev"