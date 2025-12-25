"""
Тесты для проверки доступности статических файлов frontend-v2.7.
"""
import pytest
import sys
from pathlib import Path
from fastapi.testclient import TestClient

# Добавляем путь к backend модулю
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app

client = TestClient(app)


def test_v27_index():
    """Проверка доступности главной страницы v2.7."""
    response = client.get("/v2.7")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Шахматы 2.7" in response.text


def test_v27_css():
    """Проверка доступности CSS файла."""
    response = client.get("/v2.7/static/style.css")
    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"] or "stylesheet" in response.headers.get("content-type", "")


def test_v27_game_js():
    """Проверка доступности game.js."""
    response = client.get("/v2.7/game.js")
    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"] or "javascript" in response.headers.get("content-type", "")


def test_v27_static_js_files():
    """Проверка доступности JS файлов из static/."""
    js_files = ["animations.js", "pgn-exporter.js", "sound-manager.js"]
    for js_file in js_files:
        response = client.get(f"/v2.7/static/{js_file}")
        assert response.status_code == 200, f"Файл {js_file} недоступен"
        assert "javascript" in response.headers.get("content-type", "").lower() or "application/javascript" in response.headers.get("content-type", "")

