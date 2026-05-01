#!/usr/bin/env python3
"""
Add More Checklist Types to Production Database
Creates diverse checklist types for better variety
"""

import os
import sys
import uuid
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def main():
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        print("🔧 Adding more checklist types to production...")
        
        # Check current types
        current_types = conn.execute(text("""
            SELECT id, name, code FROM checklist_types ORDER BY name
        """)).all()
        
        print(f"Current checklist types ({len(current_types)}):")
        for type_id, name, code in current_types:
            print(f"  - {name} ({code})")
        
        # Define new checklist types to add
        new_types = [
            {
                "name": "ISO Compliance",
                "code": "iso_compliance", 
                "description": "ISO standards compliance checklist"
            },
            {
                "name": "Security Audit",
                "code": "security_audit",
                "description": "Security and cybersecurity audit checklist"
            },
            {
                "name": "GDPR Compliance",
                "code": "gdpr_compliance",
                "description": "GDPR data protection compliance checklist"
            },
            {
                "name": "Quality Assurance",
                "code": "quality_assurance",
                "description": "Quality control and assurance checklist"
            },
            {
                "name": "Risk Assessment",
                "code": "risk_assessment",
                "description": "Risk management and assessment checklist"
            },
            {
                "name": "Financial Audit",
                "code": "financial_audit",
                "description": "Financial accounting and audit checklist"
            },
            {
                "name": "Health & Safety",
                "code": "health_safety",
                "description": "Occupational health and safety checklist"
            },
            {
                "name": "Environmental Compliance",
                "code": "environmental",
                "description": "Environmental regulations compliance checklist"
            }
        ]
        
        print(f"\n➕ Adding {len(new_types)} new checklist types...")
        
        added_count = 0
        for new_type in new_types:
            # Check if type already exists
            existing = conn.execute(text("""
                SELECT id FROM checklist_types WHERE code = :code
            """), {"code": new_type["code"]}).fetchone()
            
            if existing:
                print(f"  ⏭️  {new_type['name']} ({new_type['code']}) - already exists")
                continue
            
            # Insert new type
            conn.execute(text("""
                INSERT INTO checklist_types (id, name, code, description, is_active, created_at, updated_at)
                VALUES (:id, :name, :code, :description, true, NOW(), NOW())
            """), {
                "id": str(uuid.uuid4()),
                "name": new_type["name"],
                "code": new_type["code"],
                "description": new_type["description"]
            })
            
            print(f"  ✅ {new_type['name']} ({new_type['code']}) - added")
            added_count += 1
        
        conn.commit()
        print(f"\n🎉 Successfully added {added_count} new checklist types!")
        
        # Show updated types
        updated_types = conn.execute(text("""
            SELECT id, name, code FROM checklist_types ORDER BY name
        """)).all()
        
        print(f"\n📊 Updated checklist types ({len(updated_types)}):")
        for type_id, name, code in updated_types:
            print(f"  - {name} ({code})")
        
        # Now redistribute checklists across all types
        print(f"\n🔄 Redistributing checklists across {len(updated_types)} types...")
        
        # Get all published checklists
        checklists = conn.execute(text("""
            SELECT c.id, COALESCE(ct.title, 'No title') as title, c.checklist_type_id
            FROM checklists c
            LEFT JOIN checklist_translations ct ON c.id = ct.checklist_id
            WHERE c.status_code_id = 2
            ORDER BY c.created_at DESC
        """)).all()
        
        updates = 0
        for i, (checklist_id, title, current_type_id) in enumerate(checklists):
            # Cycle through all types
            new_type_id, new_type_name, new_type_code = updated_types[i % len(updated_types)]
            
            # Only update if it's different
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
        print(f"\n🎉 Updated {updates} checklists with new types!")
        
        # Show final distribution
        final_dist = conn.execute(text("""
            SELECT ct.name, COUNT(c.id) as count
            FROM checklists c
            JOIN checklist_types ct ON c.checklist_type_id = ct.id
            WHERE c.status_code_id = 2
            GROUP BY ct.name
            ORDER BY count DESC
        """)).all()
        
        print(f"\n📊 Final type distribution:")
        for type_name, count in final_dist:
            print(f"  {type_name}: {count} checklists")
        
        conn.close()
        print(f"\n✅ Production checklist types diversified successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
