#!/usr/bin/env python3
"""
Debug Question Image Issues

This script helps diagnose why images disappear after saving questions.
It tests:
1. Image upload functionality
2. Question creation with images
3. Image preview API
4. Database records
"""

import os
import sys
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from uuid import UUID

# Database configuration
DATABASE_URL = "postgresql://checklist:checklistkb@localhost:5432/checklist"

def main():
    engine = create_engine(DATABASE_URL)
    conn = engine.connect()
    
    print("🔧 Debugging Question Image Issues")
    print("=" * 50)
    
    try:
        # Test 1: Check if there are any media files
        print("\n📊 Test 1: Check media files in database")
        media_count = conn.execute(text("SELECT COUNT(*) FROM media")).scalar()
        print(f"  Total media files: {media_count}")
        
        if media_count > 0:
            media_files = conn.execute(text("""
                SELECT id, filename, original_filename, media_type, is_active, scan_status, created_at
                FROM media 
                ORDER BY created_at DESC 
                LIMIT 5
            """)).all()
            
            print(f"  Recent media files:")
            for media in media_files:
                print(f"    ID: {media[0]}")
                print(f"    Filename: {media[1]} ({media[2]})")
                print(f"    Type: {media[3]}, Active: {media[4]}, Scan: {media[5]}")
                print(f"    Created: {media[6]}")
                print()
        else:
            print("  ❌ No media files found")
        
        # Test 2: Check questions with illustrative images
        print("\n📋 Test 2: Check questions with illustrative images")
        questions_with_images = conn.execute(text("""
            SELECT q.id, q.question_code, q.illustrative_image_id, 
                   m.filename as image_filename, m.is_active as image_active
            FROM checklist_questions q
            LEFT JOIN media m ON q.illustrative_image_id = m.id
            WHERE q.illustrative_image_id IS NOT NULL
            ORDER BY q.created_at DESC
            LIMIT 5
        """)).all()
        
        print(f"  Questions with images: {len(questions_with_images)}")
        for question in questions_with_images:
            print(f"    Question ID: {question[0]}")
            print(f"    Question Code: {question[1]}")
            print(f"    Image ID: {question[2]}")
            print(f"    Image Filename: {question[3]}")
            print(f"    Image Active: {question[4]}")
            print()
        
        # Test 3: Check answer options with images
        print("\n📝 Test 3: Check answer options with illustrative images")
        options_with_images = conn.execute(text("""
            SELECT ao.id, ao.label, ao.illustrative_image_id,
                   m.filename as image_filename, m.is_active as image_active
            FROM checklist_question_answer_options ao
            LEFT JOIN media m ON ao.illustrative_image_id = m.id
            WHERE ao.illustrative_image_id IS NOT NULL
            ORDER BY ao.created_at DESC
            LIMIT 5
        """)).all()
        
        print(f"  Answer options with images: {len(options_with_images)}")
        for option in options_with_images:
            print(f"    Option ID: {option[0]}")
            print(f"    Label: {option[1]}")
            print(f"    Image ID: {option[2]}")
            print(f"    Image Filename: {option[3]}")
            print(f"    Image Active: {option[4]}")
            print()
        
        # Test 4: Test image preview API paths
        print("\n🔗 Test 4: Image preview API paths")
        if media_files:
            for media in media_files[:3]:  # Test first 3 media files
                media_id = media[0]
                preview_path = f"/api/api/v1/media/{media_id}/preview"
                print(f"  Preview path: {preview_path}")
                print(f"    Media ID: {media_id}")
                print(f"    Filename: {media[1]}")
                print(f"    Active: {media[4]}, Scan: {media[5]}")
                
                # Check if file exists on disk
                try:
                    file_path_query = text("SELECT file_path FROM media WHERE id = :media_id")
                    result = conn.execute(file_path_query, {"media_id": media_id}).scalar()
                    if result:
                        import os
                        exists = os.path.exists(result)
                        print(f"    File exists: {exists} ({result})")
                    else:
                        print(f"    ❌ No file path in database")
                except Exception as e:
                    print(f"    ❌ Error checking file path: {e}")
                print()
        
        # Test 5: Check for recent question creation activity
        print("\n📈 Test 5: Recent question creation activity")
        recent_questions = conn.execute(text("""
            SELECT q.id, q.question_code, q.illustrative_image_id, q.created_at,
                   COUNT(ao.id) as answer_options_count
            FROM checklist_questions q
            LEFT JOIN checklist_question_answer_options ao ON q.id = ao.question_id
            WHERE q.created_at >= NOW() - INTERVAL '24 hours'
            GROUP BY q.id, q.question_code, q.illustrative_image_id, q.created_at
            ORDER BY q.created_at DESC
            LIMIT 5
        """)).all()
        
        print(f"  Questions created in last 24h: {len(recent_questions)}")
        for question in recent_questions:
            print(f"    Question: {question[1]} (ID: {question[0]})")
            print(f"    Has image: {'Yes' if question[2] else 'No'}")
            print(f"    Answer options: {question[4]}")
            print(f"    Created: {question[3]}")
            print()
        
        # Test 6: Diagnose common issues
        print("\n🔍 Test 6: Common issue diagnosis")
        
        # Check for inactive media that might be referenced
        inactive_media_refs = conn.execute(text("""
            SELECT COUNT(*) FROM checklist_questions q
            JOIN media m ON q.illustrative_image_id = m.id
            WHERE q.illustrative_image_id IS NOT NULL AND m.is_active = false
        """)).scalar()
        
        if inactive_media_refs > 0:
            print(f"  ⚠️  Found {inactive_media_refs} questions referencing inactive media")
        else:
            print(f"  ✅ No questions referencing inactive media")
        
        # Check for missing files
        missing_files = conn.execute(text("""
            SELECT COUNT(*) FROM media m
            WHERE m.is_active = true 
            AND NOT EXISTS (SELECT 1 FROM pg_stat_file(m.file_path))
        """)).scalar()
        
        if missing_files > 0:
            print(f"  ⚠️  Found {missing_files} active media with missing files")
        else:
            print(f"  ✅ No missing files detected")
        
        # Check for non-image media
        non_image_media = conn.execute(text("""
            SELECT COUNT(*) FROM media m
            WHERE m.is_active = true AND m.media_type != 'image'
        """)).scalar()
        
        if non_image_media > 0:
            print(f"  ⚠️  Found {non_image_media} non-image media files")
        else:
            print(f"  ✅ All active media are images")
        
        print("\n🎯 Recommendations:")
        if media_count == 0:
            print("  - Upload some test images to verify the upload process")
        if len(questions_with_images) == 0:
            print("  - Create a test question with an illustrative image")
        if missing_files > 0:
            print("  - Fix missing media files on disk")
        if inactive_media_refs > 0:
            print("  - Activate referenced media files")
        
        print(f"\n✅ Diagnostic completed!")
        
    except Exception as e:
        print(f"\n❌ Error during diagnosis: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
