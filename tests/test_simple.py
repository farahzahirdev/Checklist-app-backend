"""
Simple test to debug the health endpoint issue
"""
from fastapi.testclient import TestClient
from app.main import app

def test_health_simple():
    """Simple health test"""
    client = TestClient(app)
    response = client.get("/api/v1/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.text}")
    assert response.status_code == 200

if __name__ == "__main__":
    test_health_simple()
