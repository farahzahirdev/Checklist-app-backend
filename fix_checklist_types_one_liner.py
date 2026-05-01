#!/usr/bin/env python3
"""
One-liner production checklist type fix
Replace DATABASE_URL and run: python fix_checklist_types_one_liner.py
"""

import os
import sys
from sqlalchemy import create_engine, text

# UPDATE THIS: Your production database URL
DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def main():
    if "username:password" in DATABASE_URL:
        print("❌ Please update DATABASE_URL in this file with your production database credentials")
        sys.exit(1)
    
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        print("🔧 Fixing checklist types in production...")
        
        # Get available types (excluding the problematic one)
        types = conn.execute(text("""
            SELECT id, name FROM checklist_types 
            WHERE id != '6f93c47f-edbc-4550-99a0-047c55015b6b' 
            ORDER BY name LIMIT 5
        """)).all()
        
        # Get checklists to fix
        checklists = conn.execute(text("""
            SELECT id, title FROM checklists 
            WHERE status_code_id = 2 AND checklist_type_id = '6f93c47f-edbc-4550-99a0-047c55015b6b'
            ORDER BY created_at DESC
        """)).all()
        
        print(f"Found {len(checklists)} checklists to fix with {len(types)} available types")
        
        # Update checklists with different types
        for i, (checklist_id, title) in enumerate(checklists):
            if i >= len(types):
                break
            new_type_id, new_type_name = types[i]
            
            conn.execute(text("""
                UPDATE checklists SET checklist_type_id = :new_type_id 
                WHERE id = :checklist_id
            """), {'new_type_id': new_type_id, 'checklist_id': checklist_id})
            
            print(f"  ✅ {title[:30]} → {new_type_name}")
        
        conn.commit()
        print(f"🎉 Updated {min(len(checklists), len(types))} checklists!")
        
        # Verify
        result = conn.execute(text("""
            SELECT COUNT(DISTINCT checklist_type_id) 
            FROM checklists WHERE status_code_id = 2
        """)).scalar()
        
        print(f"✅ Now have {result} different checklist types in production!")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
