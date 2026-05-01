#!/usr/bin/env python3
"""
Verify Audit Filter Fix

This script verifies that the audit log search filter fix is working
by testing the enum casting issue we resolved.
"""

import os
import sys
from sqlalchemy import create_engine, text, String, cast
from sqlalchemy.orm import Session

# Database configuration  
DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def test_enum_casting_fix():
    """Test that the enum casting fix works"""
    
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    
    print("🔧 Testing Audit Log Enum Casting Fix")
    print("=" * 50)
    
    try:
        # Test 1: Check if action column is enum type
        print("\n📊 Test 1: Check action column type")
        column_info = conn.execute(text("""
            SELECT column_name, data_type, udt_name 
            FROM information_schema.columns 
            WHERE table_name = 'audit_logs' AND column_name = 'action'
        """)).fetchone()
        
        if column_info:
            print(f"  Action column type: {column_info[1]} ({column_info[2]})")
            if column_info[2] == 'audit_action':
                print("  ✅ Confirmed: action column is enum type 'audit_action'")
            else:
                print(f"  ⚠️  Unexpected type: {column_info[2]}")
        
        # Test 2: Test the OLD way (should fail)
        print("\n❌ Test 2: OLD way (direct ILIKE on enum)")
        try:
            old_way = conn.execute(text("""
                SELECT COUNT(*) FROM audit_logs 
                WHERE action ILIKE '%login%'
            """)).scalar()
            print(f"  ❌ OLD way worked unexpectedly: {old_way} (should have failed)")
        except Exception as e:
            print(f"  ✅ OLD way failed as expected: {str(e)[:100]}...")
        
        # Test 3: Test the NEW way (should work)
        print("\n✅ Test 3: NEW way (cast enum to string)")
        try:
            new_way = conn.execute(text("""
                SELECT COUNT(*) FROM audit_logs 
                WHERE action::text ILIKE '%login%'
            """)).scalar()
            print(f"  ✅ NEW way worked: {new_way} logs found")
        except Exception as e:
            print(f"  ❌ NEW way failed: {e}")
            return False
        
        # Test 4: Test our fixed search query
        print("\n🔍 Test 4: Fixed search query with multiple fields")
        try:
            search_query = conn.execute(text("""
                SELECT COUNT(*) FROM audit_logs 
                WHERE changes_summary ILIKE '%login%' OR 
                      target_entity ILIKE '%user%' OR 
                      action::text ILIKE '%login%' OR 
                      error_message ILIKE '%login%'
            """)).scalar()
            print(f"  ✅ Fixed search query worked: {search_query} logs found")
        except Exception as e:
            print(f"  ❌ Fixed search query failed: {e}")
            return False
        
        # Test 5: Test with actual search term 't' (from your error)
        print("\n🔍 Test 5: Search with term 't' (your original error)")
        try:
            search_t = conn.execute(text("""
                SELECT COUNT(*) FROM audit_logs 
                WHERE changes_summary ILIKE '%t%' OR 
                      target_entity ILIKE '%t%' OR 
                      action::text ILIKE '%t%' OR 
                      error_message ILIKE '%t%'
            """)).scalar()
            print(f"  ✅ Search 't' worked: {search_t} logs found")
        except Exception as e:
            print(f"  ❌ Search 't' failed: {e}")
            return False
        
        # Test 6: Show sample actions that would be found
        print("\n📋 Test 6: Sample actions containing 't'")
        sample_actions = conn.execute(text("""
            SELECT DISTINCT action, COUNT(*) as count
            FROM audit_logs 
            WHERE action::text ILIKE '%t%'
            GROUP BY action
            ORDER BY count DESC
            LIMIT 5
        """)).all()
        
        print(f"  Actions containing 't':")
        for action, count in sample_actions:
            print(f"    {action}: {count} logs")
        
        print("\n✅ Enum casting fix is working correctly!")
        return True
        
    except Exception as e:
        print(f"\n❌ Error testing enum casting: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def test_service_layer_fix():
    """Test that the service layer fix is in place"""
    
    print("\n🔧 Testing Service Layer Fix")
    print("=" * 30)
    
    # Check the actual service file
    service_file = "/home/ec2-user/apps/mvp-app-backend/app/services/audit_log.py"
    
    try:
        with open(service_file, 'r') as f:
            content = f.read()
        
        # Check for the fix
        if "AuditLog.action.cast(String).ilike(search_term)" in content:
            print("✅ Service layer fix is in place")
            print("✅ Found: AuditLog.action.cast(String).ilike(search_term)")
        else:
            print("❌ Service layer fix NOT found")
            return False
        
        # Check for String import
        if "from sqlalchemy import" in content and "String" in content:
            print("✅ String import is present")
        else:
            print("❌ String import missing")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking service file: {e}")
        return False

if __name__ == "__main__":
    print("🚀 Verifying Audit Filter Fix")
    
    # Test 1: Database enum casting
    db_success = test_enum_casting_fix()
    
    # Test 2: Service layer fix
    service_success = test_service_layer_fix()
    
    if db_success and service_success:
        print(f"\n🎉 Audit filter fix verification completed successfully!")
        print(f"✅ Database enum casting works")
        print(f"✅ Service layer fix is in place")
        print(f"✅ Search filter should work now")
    else:
        print(f"\n❌ Some verification tests failed")
        sys.exit(1)
