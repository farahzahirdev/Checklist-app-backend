# CMS Seed Script

This script seeds the CMS database with default content for all public pages in both English and Czech.

## Pages Seeded

The seed script creates the following pages with both Czech (cs) and English (en) versions:

1. **about-us** - About page with mission statement
2. **contact** - Contact page with support information
3. **faq** - FAQ page
4. **products** - Products/services page
5. **resources-public** - Resources and guides page
6. **privacy-policy** - Privacy policy (legal page)
7. **terms-of-service** - Terms of service (legal page)
8. **cookies** - Cookie policy (legal page)

## How to Run

### Prerequisites

- Python 3.11+
- Virtual environment activated with dependencies installed
- Database migrations applied (`alembic upgrade head`)
- At least one admin user in the database

### Run the Seed Script

```bash
# Navigate to the API directory
cd /home/ec2-user/apps/mvp-app-backend

# Activate virtual environment
source venv/bin/activate

# Run the seed script
python seed_cms.py
```

### Expected Output

```
✓ Using admin user: admin
✓ Seeded about-us (en)
✓ Seeded about-us (cs)
✓ Seeded contact (en)
✓ Seeded contact (cs)
...
✅ Successfully seeded 16 pages into CMS
```

## What the Seed Does

1. Fetches the first admin user from the database
2. Creates a Page record for each slug + language combination
3. Adds default sections to each page (hero, standard, or legal)
4. Populates sections with default content in the respective language
5. Marks all pages as "published" by default

## After Seeding

Once seeded, you can:

1. **View pages** in the admin CMS dashboard at `/admin/cms`
2. **Edit content** by clicking on any page in the list
3. **Manage sections** within each page
4. **Upload images** via the Image Manager
5. **Publish/unpublish** pages as needed

## Content Management

- Pages follow a fallback pattern: CMS content is shown if available, otherwise the hardcoded frontend content is used
- All pages are seeded in "published" status
- To modify content, use the admin dashboard, not this script
- The script safely skips seeding if pages already exist

## Language Support

- **Czech (cs)** - All pages have Czech translations
- **English (en)** - All pages have English translations
- Default language in queries: English (en)

## Troubleshooting

### "No admin user found in database"
- Ensure you've created at least one admin user before running the seed script
- You can create an admin user via the application signup flow

### "CMS already contains X pages. Skipping seed"
- The database already has CMS content
- To reset, delete all records from `cms_pages` table and run again

### Database Connection Error
- Ensure the FastAPI backend is running
- Check `app/core/config.py` for database configuration
- Verify `.env` file has correct database credentials
