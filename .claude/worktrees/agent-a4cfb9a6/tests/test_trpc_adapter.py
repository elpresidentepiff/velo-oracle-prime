"""
Tests for tRPC Compatibility Adapter

Tests the tRPC wrapper endpoints to ensure they properly translate
between tRPC request/response format and FastAPI endpoints.

Date: 2026-01-06
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch
from datetime import date, datetime

# We'll mock the database and storage clients
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

class TestTRPCAdapter:
    """Test suite for tRPC adapter endpoints"""
    
    def test_trpc_create_batch_success(self, client, mock_app):
        """Test successful batch creation via tRPC"""
        # Mock the database response
        mock_app.state.db.get_batch_by_date = AsyncMock(return_value=None)
        mock_app.state.db.create_batch = AsyncMock(return_value={
            'id': 'test-batch-id',
            'status': 'uploaded',
            'created_at': datetime.now()
        })
        
        # tRPC request format
        trpc_request = {
            "input": {
                "import_date": "2026-01-06",
                "source": "racing_post",
                "notes": "Test batch"
            }
        }
        
        response = client.post("/trpc/ingestion.createBatch", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC response format
        assert "result" in data
        assert "data" in data["result"]
        assert data["result"]["data"]["batch_id"] == "test-batch-id"
        assert data["result"]["data"]["status"] == "uploaded"
    
    def test_trpc_create_batch_error(self, client, mock_app):
        """Test error handling in createBatch"""
        # Mock the database to raise an error
        mock_app.state.db.get_batch_by_date = AsyncMock(side_effect=Exception("Database error"))
        
        trpc_request = {
            "input": {
                "import_date": "2026-01-06",
                "source": "racing_post"
            }
        }
        
        response = client.post("/trpc/ingestion.createBatch", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC error format
        assert "error" in data
        assert "message" in data["error"]
        assert "code" in data["error"]
        assert data["error"]["code"] == "INTERNAL_SERVER_ERROR"
    
    def test_trpc_get_batch_status_success(self, client, mock_app):
        """Test successful batch status retrieval via tRPC"""
        # Mock the database responses
        mock_app.state.db.get_batch_by_id = AsyncMock(return_value={
            'id': 'test-batch-id',
            'import_date': date(2026, 1, 6),
            'source': 'racing_post',
            'status': 'ready',
            'created_at': datetime.now(),
            'updated_at': datetime.now()
        })
        mock_app.state.db.get_batch_files = AsyncMock(return_value=[])
        mock_app.state.db.get_batch_stats = AsyncMock(return_value={
            'races_count': 10,
            'runners_count': 100
        })
        
        trpc_request = {
            "input": {
                "batch_id": "test-batch-id"
            }
        }
        
        response = client.post("/trpc/ingestion.getBatchStatus", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC response format
        assert "result" in data
        assert "data" in data["result"]
        assert data["result"]["data"]["batch_id"] == "test-batch-id"
        assert data["result"]["data"]["status"] == "ready"
    
    def test_trpc_get_batch_status_missing_batch_id(self, client):
        """Test error when batch_id is missing"""
        trpc_request = {
            "input": {}
        }
        
        response = client.post("/trpc/ingestion.getBatchStatus", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC error format
        assert "error" in data
        assert "batch_id is required" in data["error"]["message"]
    
    def test_trpc_list_races_success(self, client, mock_app):
        """Test successful race listing via tRPC"""
        # Mock the database response
        mock_app.state.db.get_races_by_date = AsyncMock(return_value=[
            {'race_id': 'race-1', 'course': 'Ascot'},
            {'race_id': 'race-2', 'course': 'Kempton'}
        ])
        
        trpc_request = {
            "input": {
                "import_date": "2026-01-06"
            }
        }
        
        response = client.post("/trpc/ingestion.listRaces", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC response format
        assert "result" in data
        assert "data" in data["result"]
        assert data["result"]["data"]["races_count"] == 2
        assert len(data["result"]["data"]["races"]) == 2
    
    def test_trpc_list_races_invalid_date(self, client):
        """Test error with invalid date format"""
        trpc_request = {
            "input": {
                "import_date": "invalid-date"
            }
        }
        
        response = client.post("/trpc/ingestion.listRaces", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC error format
        assert "error" in data
        assert "Invalid date format" in data["error"]["message"]
    
    def test_trpc_get_race_details_success(self, client, mock_app):
        """Test successful race details retrieval via tRPC"""
        # Mock the database responses
        mock_app.state.db.get_race_by_id = AsyncMock(return_value={
            'race_id': 'race-1',
            'course': 'Ascot',
            'off_time': '14:30'
        })
        mock_app.state.db.get_race_runners = AsyncMock(return_value=[
            {'horse_name': 'Thunder', 'jockey': 'Smith'},
            {'horse_name': 'Lightning', 'jockey': 'Jones'}
        ])
        
        trpc_request = {
            "input": {
                "race_id": "race-1"
            }
        }
        
        response = client.post("/trpc/ingestion.getRaceDetails", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC response format
        assert "result" in data
        assert "data" in data["result"]
        assert data["result"]["data"]["race"]["race_id"] == "race-1"
        assert data["result"]["data"]["runner_count"] == 2
    
    def test_trpc_register_files_missing_batch_id(self, client):
        """Test error when batch_id is missing in registerFiles"""
        trpc_request = {
            "input": {
                "files": []
            }
        }
        
        response = client.post("/trpc/ingestion.registerFiles", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC error format
        assert "error" in data
        assert "batch_id is required" in data["error"]["message"]
    
    def test_trpc_parse_batch_missing_batch_id(self, client):
        """Test error when batch_id is missing in parseBatch"""
        trpc_request = {
            "input": {}
        }
        
        response = client.post("/trpc/ingestion.parseBatch", json=trpc_request)
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify tRPC error format
        assert "error" in data
        assert "batch_id is required" in data["error"]["message"]
    
    def test_trpc_endpoints_accept_get_requests(self, client):
        """Test that tRPC endpoints accept GET requests (tRPC spec)"""
        # GET requests should be accepted (even if they don't have input)
        response = client.get("/trpc/ingestion.listRaces")
        # Should not return 405 Method Not Allowed
        assert response.status_code in [200, 400]
        
        response = client.get("/trpc/ingestion.getBatchStatus")
        assert response.status_code in [200, 400]
