#!/usr/bin/env python3

import os
import sys
import requests
from pathlib import Path

# Add the app directory to Python path
app_dir = Path(__file__).parent / "app"
sys.path.insert(0, str(app_dir))

from app.db.session import get_db
from app.models.user import User
from sqlalchemy import select

def get_user_token():
    """Get a valid auth token for testing"""
    try:
        db = next(get_db())
        user = db.execute(select(User).limit(1)).scalar_one()
        print(f"Testing with user: {user.id}")
        
        # You'll need to get a real token from your login endpoint
        # For now, let's test the API endpoint directly
        return user.id
    except Exception as e:
        print(f"Error getting user: {e}")
        return None

def test_payment_status_api(user_id):
    """Test the payment status API endpoint"""
    try:
        # Test the API endpoint that frontend calls
        url = f"http://localhost:8000/api/v1/payments/users/{user_id}/status"
        
        # You'll need to add proper auth headers
        headers = {
            "Authorization": "Bearer YOUR_TOKEN_HERE",
            "Content-Type": "application/json"
        }
        
        print(f"Testing API endpoint: {url}")
        print("Note: You'll need to add a valid auth token")
        
        # For now, let's check if the endpoint is reachable
        response = requests.get(url, headers=headers, timeout=5)
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API - is it running?")
    except Exception as e:
        print(f"❌ Error testing API: {e}")

if __name__ == "__main__":
    user_id = get_user_token()
    if user_id:
        test_payment_status_api(user_id)
