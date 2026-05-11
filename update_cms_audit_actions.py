#!/usr/bin/env python3
"""
Script to update the audit_action enum in the database to include CMS actions.
"""

import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import text
from app.db.session import engine

def update_audit_actions_enum():
    """Update the audit_action enum to include CMS actions."""
    
    cms_actions = [
        'cms_page_create',
        'cms_page_update', 
        'cms_page_delete',
        'cms_page_publish',
        'cms_section_create',
        'cms_section_update',
        'cms_section_delete',
        'cms_image_upload',
        'cms_image_update',
        'cms_image_delete'
    ]
    
    with engine.connect() as conn:
        # Get current enum values
        result = conn.execute(text("""
            SELECT enumlabel as value 
            FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'audit_action')
            ORDER BY enumlabel
        """))
        current_values = [row[0] for row in result.fetchall()]
        
        print(f"Current enum values: {current_values}")
        
        # Add missing CMS actions
        missing_actions = [action for action in cms_actions if action not in current_values]
        
        if missing_actions:
            print(f"Adding missing CMS actions: {missing_actions}")
            
            for action in missing_actions:
                conn.execute(text(f"""
                    ALTER TYPE audit_action ADD VALUE '{action}'
                """))
            
            conn.commit()
            print("CMS audit actions added successfully!")
        else:
            print("All CMS audit actions already exist!")
        
        # Verify the update
        result = conn.execute(text("""
            SELECT enumlabel as value 
            FROM pg_enum 
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'audit_action')
            ORDER BY enumlabel
        """))
        updated_values = [row[0] for row in result.fetchall()]
        
        print(f"Updated enum values: {updated_values}")

if __name__ == "__main__":
    update_audit_actions_enum()
