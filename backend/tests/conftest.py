"""Test config — isolate the DB to a temp SQLite file before any app import."""
import os
import tempfile

_fd, _path = tempfile.mkstemp(suffix=".db", prefix="obradoriq_test_")
os.close(_fd)
os.environ["DATABASE_URL"] = f"sqlite:///{_path}"
os.environ["LLM_OFFLINE"] = "true"
os.environ["JWT_SECRET"] = "test-secret"
