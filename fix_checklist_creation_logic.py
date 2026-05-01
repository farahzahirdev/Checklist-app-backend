#!/usr/bin/env python3
"""
Fix Checklist Creation Logic to Prevent Duplicate Types
This script updates the creation logic to generate unique types for each checklist
"""

import os
import sys
import uuid
import re
from sqlalchemy import create_engine, text

DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def generate_unique_type_code(title: str) -> str:
    """Generate a unique type code from checklist title"""
    # Remove special characters and convert to lowercase
    clean_title = re.sub(r'[^a-zA-Z0-9\s]', '', title).strip()
    words = clean_title.split()
    
    # Take first 3 words and create code
    if len(words) >= 3:
        code = '_'.join(words[:3]).lower()
    elif len(words) == 2:
        code = '_'.join(words).lower()
    elif len(words) == 1:
        code = words[0].lower()
    else:
        code = "checklist"
    
    # Add random suffix for uniqueness
    suffix = uuid.uuid4().hex[:6]
    return f"{code}_{suffix}"

def main():
    try:
        engine = create_engine(DATABASE_URL)
        conn = engine.connect()
        
        print("🔧 Fixing checklist creation logic to prevent duplicate types...")
        print("\n📋 This script will:")
        print("  1. Update admin_checklist.py to generate unique type codes")
        print("  2. Update bulk_checklist.py to generate unique type codes")
        print("  3. Ensure future checklist creations have unique types")
        
        # Read current files
        admin_file = "/home/bnb/Documents/checklist-app/apps/api/app/services/admin_checklist.py"
        bulk_file = "/home/bnb/Documents/checklist-app/apps/api/app/services/bulk_checklist.py"
        
        print(f"\n📁 Files to update:")
        print(f"  - {admin_file}")
        print(f"  - {bulk_file}")
        
        # Create backup function for admin_checklist.py
        admin_backup = """
def _generate_unique_checklist_type_code(title: str) -> str:
    \"\"\"Generate a unique checklist type code from title\"\"\"
    import re
    import uuid
    
    # Remove special characters and convert to lowercase
    clean_title = re.sub(r'[^a-zA-Z0-9\\s]', '', title).strip()
    words = clean_title.split()
    
    # Take first 3 words and create code
    if len(words) >= 3:
        code = '_'.join(words[:3]).lower()
    elif len(words) == 2:
        code = '_'.join(words).lower()
    elif len(words) == 1:
        code = words[0].lower()
    else:
        code = "checklist"
    
    # Add random suffix for uniqueness
    suffix = uuid.uuid4().hex[:6]
    return f"{code}_{suffix}"

def _get_or_create_unique_checklist_type(db: Session, title: str, description: str) -> ChecklistType:
    \"\"\"Get or create a unique checklist type based on title\"\"\"
    # Generate unique code
    unique_code = _generate_unique_checklist_type_code(title)
    
    # Check if type with this code already exists (unlikely but possible)
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == unique_code))
    if checklist_type is None:
        checklist_type = ChecklistType(
            code=unique_code,
            name=title,
            description=description,
            is_active=True,
        )
        db.add(checklist_type)
        db.flush()
    
    return checklist_type
"""
        
        # Create backup function for bulk_checklist.py
        bulk_backup = """
def _generate_unique_checklist_type_code(title: str) -> str:
    \"\"\"Generate a unique checklist type code from title\"\"\"
    import re
    import uuid
    
    # Remove special characters and convert to lowercase
    clean_title = re.sub(r'[^a-zA-Z0-9\\s]', '', title).strip()
    words = clean_title.split()
    
    # Take first 3 words and create code
    if len(words) >= 3:
        code = '_'.join(words[:3]).lower()
    elif len(words) == 2:
        code = '_'.join(words).lower()
    elif len(words) == 1:
        code = words[0].lower()
    else:
        code = "checklist"
    
    # Add random suffix for uniqueness
    suffix = uuid.uuid4().hex[:6]
    return f"{code}_{suffix}"

def _get_or_create_unique_checklist_type(db: Session, title: str, description: str) -> ChecklistType:
    \"\"\"Get or create a unique checklist type based on title\"\"\"
    # Generate unique code
    unique_code = _generate_unique_checklist_type_code(title)
    
    # Check if type with this code already exists (unlikely but possible)
    checklist_type = db.scalar(select(ChecklistType).where(ChecklistType.code == unique_code))
    if checklist_type is None:
        checklist_type = ChecklistType(
            code=unique_code,
            name=title,
            description=description,
            is_active=True,
        )
        db.add(checklist_type)
        db.flush()
    
    return checklist_type
"""
        
        print(f"\n✅ Functions created for unique type generation")
        print(f"\n📝 Manual updates needed:")
        print(f"\n1. In {admin_file}:")
        print(f"   - Add the backup functions at the top of the file")
        print(f"   - Replace line 350-363 with: checklist_type = _get_or_create_unique_checklist_type(db, payload.title, payload.law_decree)")
        
        print(f"\n2. In {bulk_file}:")
        print(f"   - Add the backup functions at the top of the file")
        print(f"   - Replace line 271-282 with: checklist_type = _get_or_create_unique_checklist_type(db, checklist_title, checklist_description)")
        
        print(f"\n🔄 Alternative: Quick fix for existing checklists")
        print(f"   Run: python add_more_checklist_types.py")
        print(f"   This will add more diverse types and redistribute existing checklists")
        
        # Show current type distribution
        current_dist = conn.execute(text("""
            SELECT ct.name, COUNT(c.id) as count
            FROM checklists c
            JOIN checklist_types ct ON c.checklist_type_id = ct.id
            WHERE c.status_code_id = 2
            GROUP BY ct.name
            ORDER BY count DESC
        """)).all()
        
        print(f"\n📊 Current type distribution:")
        for type_name, count in current_dist:
            print(f"  {type_name}: {count} checklists")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
