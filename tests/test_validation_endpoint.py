"""Integration tests for validation endpoint"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from datetime import date, datetime


@pytest.fixture
def mock_app():
    """Create a test FastAPI app with mocked dependencies"""
    # Mock the database and storage clients
    with patch('workers.ingestion_spine.main.get_db_client') as mock_db, \
         patch('workers.ingestion_spine.main.get_storage_client') as mock_storage:
        
        # Configure mocks
        mock_db_instance = AsyncMock()
        mock_storage_instance = AsyncMock()
        
        mock_db_instance.verify_connection = AsyncMock()
        mock_storage_instance.verify_connection = AsyncMock()
        mock_db_instance.close = AsyncMock()
        mock_storage_instance.close = AsyncMock()
        
        mock_db.return_value = mock_db_instance
        mock_storage.return_value = mock_storage_instance
        
        # Import the app after mocking
        from workers.ingestion_spine.main import app
        
        # Attach mocks to app state for test access
        app.state.db = mock_db_instance
        app.state.storage = mock_storage_instance
        
        yield app


@pytest.fixture
def client(mock_app):
    """Create a test client"""
    return TestClient(mock_app)


class TestValidationEndpoint:
    """Test suite for validation endpoint"""
    
    def test_validate_endpoint_success(self, client, mock_app):
        """Validation endpoint returns correct structure"""
        batch_id = "test-batch-1"
        
        # Mock the database methods
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [
                    {"horse_name": f"Horse {i}", "confidence": 1.0}
                    for i in range(10)
                ],
                "quality_score": 0.95,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "batch_id" in data
        assert data["batch_id"] == batch_id
        assert "total_races" in data
        assert "valid_count" in data
        assert "needs_review_count" in data
        assert "rejected_count" in data
        assert "avg_quality_score" in data
        assert "new_status" in data
        assert "races" in data
        
        # Should have called update_batch_status
        mock_app.state.db.update_batch_status.assert_called_once()
        mock_app.state.db.store_validation_report.assert_called_once()
    
    def test_validate_requires_parsed_status(self, client, mock_app):
        """Cannot validate batch that isn't parsed"""
        batch_id = "unparsed-batch"
        
        # Mock batch with 'uploaded' status
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "uploaded",
            "import_date": date(2026, 1, 8)
        })
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 400
        assert "parsed" in response.json()["detail"].lower()
    
    def test_validate_batch_not_found(self, client, mock_app):
        """Returns 404 when batch doesn't exist"""
        batch_id = "nonexistent-batch"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value=None)
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    def test_validate_batch_no_races(self, client, mock_app):
        """Returns 400 when batch has no races"""
        batch_id = "empty-batch"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[])
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 400
        assert "no races" in response.json()["detail"].lower()
    
    def test_validation_categorizes_races_correctly(self, client, mock_app):
        """Validation should correctly categorize races"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        # Mock races with different quality levels
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
                "quality_score": 0.95,
                "quality_flags": []
            },
            {
                "id": "race-2",
                "course": "Ascot",
                "distance": 1600,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(3)],
                "quality_score": 0.7,
                "quality_flags": []
            },
            {
                "id": "race-3",
                # Missing course - should be rejected
                "distance": 2000,
                "runners": [{"horse_name": "Horse 1"}],
                "quality_score": 0.8,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_races"] == 3
        assert data["valid_count"] == 1
        assert data["needs_review_count"] == 1
        assert data["rejected_count"] == 1
    
    def test_validation_updates_batch_status_needs_review(self, client, mock_app):
        """Validation should set status to needs_review when issues found"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        # Mock race that needs review
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(3)],
                "quality_score": 0.7,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["new_status"] == "needs_review"
        
        # Check that update_batch_status was called with correct status
        from workers.ingestion_spine.models import BatchStatus
        mock_app.state.db.update_batch_status.assert_called_once()
        call_args = mock_app.state.db.update_batch_status.call_args
        assert call_args[0][1] == BatchStatus.NEEDS_REVIEW
    
    def test_validation_updates_batch_status_validated(self, client, mock_app):
        """Validation should set status to validated when all valid"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        # Mock perfect race
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
                "quality_score": 0.95,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["new_status"] == "validated"
        
        # Check that update_batch_status was called with correct status
        from workers.ingestion_spine.models import BatchStatus
        mock_app.state.db.update_batch_status.assert_called_once()
        call_args = mock_app.state.db.update_batch_status.call_args
        assert call_args[0][1] == BatchStatus.VALIDATED
    
    def test_validation_stores_report(self, client, mock_app):
        """Validation should store comprehensive report"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
                "quality_score": 0.95,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        
        # Check that store_validation_report was called with proper structure
        mock_app.state.db.store_validation_report.assert_called_once()
        call_args = mock_app.state.db.store_validation_report.call_args
        report = call_args[0][1]
        
        assert "validated_at" in report
        assert "total_races" in report
        assert "valid_count" in report
        assert "needs_review_count" in report
        assert "rejected_count" in report
        assert "avg_quality_score" in report
        assert "races" in report
        assert isinstance(report["races"], list)
    
    def test_validate_accepts_ready_status(self, client, mock_app):
        """Validation should also accept 'ready' status (backward compatibility)"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "ready",  # Old status
            "import_date": date(2026, 1, 8)
        })
        
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
                "quality_score": 0.95,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
    
    def test_validation_calculates_average_quality(self, client, mock_app):
        """Validation should calculate correct average quality score"""
        batch_id = "test-batch-1"
        
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            "id": batch_id,
            "status": "parsed",
            "import_date": date(2026, 1, 8)
        })
        
        mock_app.state.db.get_batch_races = AsyncMock(return_value=[
            {
                "id": "race-1",
                "course": "Kempton",
                "distance": 2000,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(10)],
                "quality_score": 0.9,
                "quality_flags": []
            },
            {
                "id": "race-2",
                "course": "Ascot",
                "distance": 1600,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(8)],
                "quality_score": 0.8,
                "quality_flags": []
            },
            {
                "id": "race-3",
                "course": "Newmarket",
                "distance": 2400,
                "runners": [{"horse_name": f"Horse {i}"} for i in range(12)],
                "quality_score": 0.7,
                "quality_flags": []
            }
        ])
        
        mock_app.state.db.update_batch_status = AsyncMock()
        mock_app.state.db.store_validation_report = AsyncMock()
        
        response = client.post(f"/imports/{batch_id}/validate")
        
        assert response.status_code == 200
        data = response.json()
        
        # Average should be (0.9 + 0.8 + 0.7) / 3 = 0.8
        expected_avg = round((0.9 + 0.8 + 0.7) / 3, 3)
        assert data["avg_quality_score"] == expected_avg
