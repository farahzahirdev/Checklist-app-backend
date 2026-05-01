#!/usr/bin/env python3
"""
Quick Media Check - Check media files and storage
"""

import os
import subprocess

def main():
    print("🔧 Quick Media Storage Check")
    print("=" * 40)
    
    # Check if we can connect to database and get media info
    try:
        # Use psql to check media records
        cmd = [
            'psql', 
            'postgresql://checklist:checklistkb@localhost:5432/checklist',
            '-c', 
            """
            SELECT 
                id, 
                filename, 
                original_filename, 
                file_path, 
                is_active, 
                scan_status,
                created_at
            FROM media 
            WHERE is_active = true 
            ORDER BY created_at DESC 
            LIMIT 5;
            """
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("📊 Recent media files:")
            lines = result.stdout.strip().split('\n')
            for line in lines[2:]:  # Skip header
                if line.strip():
                    parts = line.split('|')
                    if len(parts) >= 6:
                        media_id = parts[0].strip()
                        filename = parts[1].strip()
                        original = parts[2].strip()
                        file_path = parts[3].strip()
                        is_active = parts[4].strip()
                        scan_status = parts[5].strip()
                        
                        print(f"  ID: {media_id}")
                        print(f"  Filename: {filename} ({original})")
                        print(f"  Path: {file_path}")
                        print(f"  Active: {is_active}, Scan: {scan_status}")
                        
                        # Check if file exists
                        if file_path:
                            exists = os.path.exists(file_path)
                            print(f"  File exists: {'✅' if exists else '❌'}")
                            if not exists:
                                print(f"  ⚠️  MISSING FILE: {file_path}")
                        print()
        else:
            print(f"❌ Database query failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
    
    # Check common media directories
    media_dirs = [
        '/home/ec2-user/apps/mvp-app-backend/media',
        '/home/ec2-user/apps/mvp-app-backend/uploads',
        '/tmp/media',
        './media',
        './uploads',
        '/var/tmp/media'
    ]
    
    print("📁 Checking media directories:")
    for dir_path in media_dirs:
        if os.path.exists(dir_path):
            files = os.listdir(dir_path)
            print(f"  ✅ {dir_path}: {len(files)} files")
            if files:
                for f in files[:3]:  # Show first 3 files
                    print(f"    - {f}")
                if len(files) > 3:
                    print(f"    ... and {len(files) - 3} more")
        else:
            print(f"  ❌ {dir_path}: Not found")
    
    print("\n🎯 Recommendations:")
    print("  1. Check media upload configuration")
    print("  2. Verify file permissions")
    print("  3. Check disk space")
    print("  4. Review media storage path in settings")

if __name__ == "__main__":
    main()
