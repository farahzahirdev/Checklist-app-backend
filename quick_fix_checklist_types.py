#!/usr/bin/env python3
"""
Quick Production Checklist Type Fix

Simple script to fix checklist types in production.
Run this on your production server.
"""

import os
import sys

# Add your database connection here
DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

try:
    import sqlalchemy as sa
    from sqlalchemy import create_engine, text
except ImportError:
    print("❌ SQLAlchemy not installed. Run: pip install sqlalchemy")
    sys.exit(1)

def main():
    print("🔧 Quick Production Checklist Type Fix")
    print("=" * 40)
    
    # Update this with your actual production database URL
    if "username:password" in DATABASE_URL:
        print("❌ Please update DATABASE_URL with your actual production database credentials")
        print("   Edit this file and replace the DATABASE_URL variable")
        sys.exit(1)
    
    try:
        # Connect to database
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        print("✅ Connected to database")
        
        # Step 1: Show current state
        print("\n📊 Current checklist type distribution:")
        result = conn.execute(text("""
            SELECT ct.name, COUNT(c.id) as count
            FROM checklist_types ct
            LEFT JOIN checklists c ON ct.id = c.checklist_type_id
            GROUP BY ct.name
            ORDER BY count DESC
        """)).all()
        
        for name, count in result:
            print(f"  {name}: {count} checklists")
        
        # Step 2: Get checklists that need fixing
        print("\n🎯 Checklists that need fixing:")
        checklists = conn.execute(text("""
            SELECT id, title
            FROM checklists
            WHERE status_code_id = 2 AND checklist_type_id = '6f93c47f-edbc-4550-99a0-047c55015b6b'
            ORDER BY created_at DESC
        """)).all()
        
        if not checklists:
            print("  ✅ No checklists need fixing!")
            return
        
        for checklist_id, title in checklists:
            print(f"  - {title[:40]} ({str(checklist_id)[:8]}...)")
        
        # Step 3: Get available types
        available_types = conn.execute(text("""
            SELECT id, name
            FROM checklist_types
            WHERE id != '6f93c47f-edbc-4550-99a0-047c55015b6b'
            ORDER BY name
            LIMIT 5
        """)).all()
        
        if len(available_types) < len(checklists):
            print(f"\n⚠️  Only {len(available_types)} alternative types available for {len(checklists)} checklists")
        
        # Step 4: Ask for confirmation
        print(f"\n❓ Ready to update {len(checklists)} checklists with different types")
        response = input("Continue? (y/N): ").strip().lower()
        
        if response != 'y':
            print("❌ Cancelled")
            return
        
        # Step 5: Update checklists
        print("\n🔧 Updating checklists...")
        updated = 0
        
        for i, (checklist_id, title) in enumerate(checklists):
            if i >= len(available_types):
                break
            
            new_type_id, new_type_name = available_types[i]
            
            conn.execute(text("""
                UPDATE checklists 
                SET checklist_type_id = :new_type_id
                WHERE id = :checklist_id
            """), {
                'new_type_id': new_type_id,
                'checklist_id': checklist_id
            })
            
            print(f"  ✅ {title[:40]:40} → {new_type_name}")
            updated += 1
        
        # Commit changes
        conn.commit()
        print(f"\n🎉 Successfully updated {updated} checklists!")
        
        # Step 6: Verify
        print("\n🔍 Verification:")
        result = conn.execute(text("""
            SELECT c.title, ct.name
            FROM checklists c
            JOIN checklist_types ct ON c.checklist_type_id = ct.id
            WHERE c.status_code_id = 2
            ORDER BY c.created_at DESC
            LIMIT 5
        """)).all()
        
        unique_types = set()
        for title, type_name in result:
            unique_types.add(type_name)
            print(f"  - {title[:40]:40} → {type_name}")
        
        print(f"\n✅ Found {len(unique_types)} different types!")
        
        conn.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
