

def test_health_endpoint_exists():
    # Lightweight import-level test — just verify the module loads
    # Full integration tests come later when services are wired up.
    from src.main import app
    assert app is not None
    assert app.title == "Semantic Search API"
