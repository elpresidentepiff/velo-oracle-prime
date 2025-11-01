"""
VÉLØ v10 - Smoke Tests
Basic sanity checks to ensure core infrastructure is working
"""

def test_smoke():
    """Basic smoke test - ensures pytest is working"""
    assert True


def test_imports():
    """Test that core modules can be imported"""
    try:
        import src
        import src.core
        import src.integrations
        import src.modules
        assert True
    except ImportError as e:
        assert False, f"Import failed: {e}"


def test_requirements():
    """Test that critical dependencies are available"""
    try:
        import pandas
        import numpy
        import sklearn
        import sqlalchemy
        import pydantic
        import alembic
        import tenacity
        import typer
        assert True
    except ImportError as e:
        assert False, f"Required dependency missing: {e}"
