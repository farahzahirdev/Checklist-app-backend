#!/usr/bin/env python3
"""
Simple test to check assessment review data
"""

import os
import sys

# Add the app directory to Python path
sys.path.insert(0, '/home/bnb/Documents/checklist-app/apps/api')

try:
    from app.db.session import SessionLocal
    from app.models.assessment_review import AssessmentReview
    from app.models.assessment import Assessment
    
    print("🔍 Testing Assessment Review Data")
    print("=" * 40)
    
    # Create database session
    db = SessionLocal()
    
    try:
        # Check if there are any assessment reviews
        review_count = db.query(AssessmentReview).count()
        print(f"📊 Total Assessment Reviews: {review_count}")
        
        if review_count > 0:
            # Get first few reviews
            reviews = db.query(AssessmentReview).limit(5).all()
            print(f"📋 Sample Reviews:")
            for i, review in enumerate(reviews, 1):
                print(f"  {i}. ID: {review.id}, Assessment: {review.assessment_id}, Status: {review.status}")
        else:
            print("❌ No assessment reviews found in database")
        
        # Check assessments
        assessment_count = db.query(Assessment).count()
        print(f"📋 Total Assessments: {assessment_count}")
        
        if assessment_count > 0:
            # Get submitted assessments
            submitted_count = db.query(Assessment).filter(Assessment.status == 'submitted').count()
            print(f"📤 Submitted Assessments: {submitted_count}")
            
            # Get recent assessments
            recent = db.query(Assessment).filter(Assessment.submitted_at.isnot(None)).limit(3).all()
            print(f"📅 Recent Assessments:")
            for i, assessment in enumerate(recent, 1):
                print(f"  {i}. ID: {assessment.id}, Status: {assessment.status}, Submitted: {assessment.submitted_at}")
        else:
            print("❌ No assessments found in database")
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
        
except ImportError as e:
    print(f"❌ Import error: {e}")
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
