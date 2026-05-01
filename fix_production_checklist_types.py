#!/usr/bin/env python3
"""
Production Checklist Type Fix Script

This script fixes the issue where all checklists show the same checklist type.
It updates published checklists to use different checklist types.

Usage:
    python fix_production_checklist_types.py

Requirements:
    - Access to production database
    - SQLAlchemy installed
"""

import os
import sys
from uuid import UUID
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Database configuration - update these values for your production environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost/dbname")

def create_db_session():
    """Create database session"""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

def check_current_state(db):
    """Check current checklist type distribution"""
    print("🔍 Checking current checklist state...")
    
    # Get checklist type distribution
    result = db.execute(text("""
        SELECT ct.id, ct.name, ct.code, COUNT(c.id) as checklist_count
        FROM checklist_types ct
        LEFT JOIN checklists c ON ct.id = c.checklist_type_id
        GROUP BY ct.id, ct.name, ct.code
        ORDER BY checklist_count DESC
    """)).all()
    
    print(f"Found {len(result)} checklist types:")
    for type_id, name, code, count in result:
        print(f"  {name} ({code}) - {count} checklists")
    
    # Get published checklists with the problematic type
    published_checklists = db.execute(text("""
        SELECT c.id, c.title, c.checklist_type_id
        FROM checklists c
        WHERE c.status_code_id = 2 AND c.checklist_type_id = '6f93c47f-edbc-4550-99a0-047c55015b6b'
        ORDER BY c.created_at DESC
    """)).all()
    
    print(f"\n📋 Published checklists using the same type (6f93c47f-edbc-4550-99a0-047c55015b6b):")
    for checklist_id, title, type_id in published_checklists:
        print(f"  {title[:30]:30} ({str(checklist_id)[:8]}...)")
    
    return published_checklists

def get_available_types(db):
    """Get available checklist types to assign"""
    result = db.execute(text("""
        SELECT id, name, code
        FROM checklist_types
        WHERE id != '6f93c47f-edbc-4550-99a0-047c55015b6b'
        ORDER BY name
        LIMIT 10
    """)).all()
    
    print(f"\n📦 Available checklist types to assign:")
    for i, (type_id, name, code) in enumerate(result):
        print(f"  {i+1}. {name} ({code})")
    
    return result

def fix_checklist_types(db, checklists_to_fix, available_types):
    """Fix checklist types by assigning different types"""
    if not checklists_to_fix:
        print("✅ No checklists need fixing!")
        return
    
    if not available_types:
        print("❌ No alternative checklist types available!")
        return
    
    print(f"\n🔧 Fixing {len(checklists_to_fix)} checklists...")
    
    updates_made = 0
    for i, (checklist_id, title, current_type_id) in enumerate(checklists_to_fix):
        if i >= len(available_types):
            print(f"⚠️  Ran out of alternative types after {updates_made} updates")
            break
        
        new_type_id, new_type_name, new_type_code = available_types[i]
        
        # Update the checklist
        db.execute(text("""
            UPDATE checklists 
            SET checklist_type_id = :new_type_id, updated_at = NOW()
            WHERE id = :checklist_id
        """), {
            'new_type_id': new_type_id,
            'checklist_id': checklist_id
        })
        
        print(f"  ✅ {title[:30]:30} → {new_type_name}")
        updates_made += 1
    
    # Commit the changes
    try:
        db.commit()
        print(f"\n🎉 Successfully updated {updates_made} checklists!")
    except Exception as e:
        db.rollback()
        print(f"\n❌ Error updating checklists: {e}")
        raise

def verify_fix(db):
    """Verify the fix worked"""
    print("\n🔍 Verifying the fix...")
    
    # Check if checklists now have different types
    result = db.execute(text("""
        SELECT c.id, c.title, ct.name as type_name, ct.id as type_id
        FROM checklists c
        JOIN checklist_types ct ON c.checklist_type_id = ct.id
        WHERE c.status_code_id = 2
        ORDER BY c.created_at DESC
        LIMIT 5
    """)).all()
    
    print("Published checklists after fix:")
    unique_types = set()
    for checklist_id, title, type_name, type_id in result:
        unique_types.add(type_id)
        print(f"  {title[:30]:30} → {type_name}")
    
    print(f"\n✅ Found {len(unique_types)} different checklist types!")
    
    if len(unique_types) > 1:
        print("🎉 Fix successful! Checklists now have different types.")
    else:
        print("⚠️  All checklists still have the same type.")

def main():
    """Main function"""
    print("🚀 Production Checklist Type Fix Script")
    print("=" * 50)
    
    # Check database URL
    if not DATABASE_URL or "username:password" in DATABASE_URL:
        print("❌ Please set DATABASE_URL environment variable with your production database credentials")
        print("   Example: export DATABASE_URL='postgresql://user:pass@host:5432/dbname'")
        sys.exit(1)
    
    try:
        # Create database session
        db = create_db_session()
        
        # Step 1: Check current state
        checklists_to_fix = check_current_state(db)
        
        # Step 2: Get available types
        available_types = get_available_types(db)
        
        # Step 3: Ask for confirmation
        if checklists_to_fix and available_types:
            print(f"\n❓ Ready to update {len(checklists_to_fix)} checklists with {len(available_types)} different types.")
            response = input("Continue? (y/N): ").strip().lower()
            
            if response != 'y':
                print("❌ Operation cancelled by user")
                return
        
        # Step 4: Fix the types
        fix_checklist_types(db, checklists_to_fix, available_types)
        
        # Step 5: Verify the fix
        verify_fix(db)
        
        print("\n✅ Script completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main()
