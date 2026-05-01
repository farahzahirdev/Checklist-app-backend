#!/usr/bin/env python3
"""
Debug script to check assessment review API and database
"""

import os
import subprocess

def main():
    print("🔍 Assessment Review API Debug")
    print("=" * 40)
    
    # Check database connection and data
    try:
        # Use psql to check review tables
        cmd = [
            'psql', 
            'postgresql://checklist:checklistkb@localhost:5432/checklist',
            '-c', 
            """
            -- Check AssessmentReview table
            SELECT 
                COUNT(*) as total_reviews,
                COUNT(CASE WHEN status IS NOT NULL THEN 1 END) as reviews_with_status,
                COUNT(DISTINCT assessment_id) as unique_assessments,
                MIN(created_at) as earliest_review,
                MAX(created_at) as latest_review
            FROM assessment_review;
            
            -- Check Assessment table
            SELECT 
                COUNT(*) as total_assessments,
                COUNT(CASE WHEN status = 'submitted' THEN 1 END) as submitted_assessments,
                COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_assessments
            FROM assessment;
            
            -- Check AssessmentAnswer table
            SELECT 
                COUNT(*) as total_answers,
                COUNT(DISTINCT assessment_id) as assessments_with_answers
            FROM assessment_answer;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📊 Database Analysis:")
            print(result.stdout)
        else:
            print(f"❌ Database query failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    # Test API endpoint directly
    try:
        import requests
        
        # Test the API endpoint
        url = "http://localhost:8000/api/v1/admin/assessment-review/assessments"
        headers = {
            "Authorization": "Bearer test-token",  # Would need real token
            "Content-Type": "application/json"
        }
        
        print(f"\n🌐 Testing API: {url}")
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"Response Type: {type(data)}")
                print(f"Response Length: {len(data) if isinstance(data, list) else 'Not a list'}")
                if isinstance(data, list) and len(data) > 0:
                    print(f"First item keys: {list(data[0].keys()) if data else 'No items'}")
                else:
                    print("Response is empty or not a list")
            except Exception as json_err:
                print(f"❌ Failed to parse JSON: {json_err}")
                print(f"Raw Response: {response.text[:500]}...")
        else:
            print(f"❌ API Error: {response.status_code}")
            print(f"Response: {response.text[:500]}...")
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")
    
    # Check recent assessment submissions
    try:
        cmd = [
            'psql', 
            'postgresql://checklist:checklistkb@localhost:5432/checklist',
            '-c', 
            """
            SELECT 
                a.id,
                a.status,
                a.submitted_at,
                u.email as user_email,
                c.title as checklist_title
            FROM assessment a
            LEFT JOIN "user" u ON a.user_id = u.id
            LEFT JOIN checklist c ON a.checklist_id = c.id
            WHERE a.submitted_at IS NOT NULL
            ORDER BY a.submitted_at DESC
            LIMIT 5;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"\n📋 Recent Assessment Submissions:")
            print(result.stdout)
        else:
            print(f"❌ Failed to check submissions: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error checking submissions: {e}")

if __name__ == "__main__":
    main()
