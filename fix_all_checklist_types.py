#!/usr/bin/env python3
"""
Complete Checklist Type Fix - Handles multiple checklists with limited types
"""

import os
import sys
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def main():
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        print("🔧 Complete checklist type fix for production...")
        
        # Get all available types
        all_types = conn.execute(text("""
            SELECT id, name, code FROM checklist_types 
            ORDER BY name
        """)).all()
        
        print(f"Found {len(all_types)} total checklist types:")
        for type_id, name, code in all_types:
            print(f"  - {name} ({code})")
        
        # Get all published checklists
        checklists = conn.execute(text("""
            SELECT c.id, COALESCE(ct.title, 'No title') as title, c.checklist_type_id
            FROM checklists c
            LEFT JOIN checklist_translations ct ON c.id = ct.checklist_id
            WHERE c.status_code_id = 2
            ORDER BY c.created_at DESC
        """)).all()
        
        print(f"\nFound {len(checklists)} published checklists")
        
        # Show current distribution
        current_dist = {}
        for checklist_id, title, type_id in checklists:
            if type_id not in current_dist:
                current_dist[type_id] = 0
            current_dist[type_id] += 1
        
        print("\nCurrent type distribution:")
        for type_id, count in current_dist.items():
            type_name = next((name for tid, name, code in all_types if tid == type_id), "Unknown")
            print(f"  {type_name}: {count} checklists")
        
        # If we have more checklists than types, we'll cycle through available types
        print(f"\n🔄 Distributing {len(checklists)} checklists across {len(all_types)} types...")
        
        updates = 0
        for i, (checklist_id, title, current_type_id) in enumerate(checklists):
            # Cycle through available types
            new_type_id, new_type_name, new_type_code = all_types[i % len(all_types)]
            
            # Only update if it's different from current
            if new_type_id != current_type_id:
                conn.execute(text("""
                    UPDATE checklists SET checklist_type_id = :new_type_id 
                    WHERE id = :checklist_id
                """), {'new_type_id': new_type_id, 'checklist_id': checklist_id})
                
                print(f"  ✅ {title[:30]:30} → {new_type_name}")
                updates += 1
            else:
                print(f"  ⏭️  {title[:30]:30} → {new_type_name} (already)")
        
        conn.commit()
        print(f"\n🎉 Updated {updates} checklists!")
        
        # Verify the fix
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT checklist_type_id) 
            FROM checklists WHERE status_code_id = 2
        """)).scalar()
        
        print(f"✅ Now have {result} different checklist types in production!")
        
        # Show final distribution
        final_dist = conn.execute(text("""
            SELECT ct.name, COUNT(c.id) as count
            FROM checklists c
            JOIN checklist_types ct ON c.checklist_type_id = ct.id
            WHERE c.status_code_id = 2
            GROUP BY ct.name
            ORDER BY count DESC
        """)).all()
        
        print("\nFinal type distribution:")
        for type_name, count in final_dist:
            print(f"  {type_name}: {count} checklists")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
