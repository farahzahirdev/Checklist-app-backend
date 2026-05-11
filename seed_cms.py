#!/usr/bin/env python3
"""
Seed script to populate CMS with existing page content in Czech and English.
Usage: python seed_cms.py
"""

import os
import sys
from uuid import uuid4
from sqlalchemy.orm import Session

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.db.session import get_db, SessionLocal
from app.models.cms import Page, PageSection
from app.core.config import get_settings

# Page content data structure
PAGES_DATA = {
    "about-us": {
        "en": {
            "title": "About Us",
            "meta_description": "Learn about our mission to help organizations achieve audit readiness",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "About Our Platform",
                        "subtitle": "Helping Organizations Achieve Audit Readiness",
                        "description": "Our platform provides comprehensive tools and guidance for organizations to prepare for audits and maintain compliance."
                    }
                },
                {
                    "section_type": "standard",
                    "order": 2,
                    "data": {
                        "title": "Our Mission",
                        "content": "We are committed to making audit preparation accessible and manageable for organizations of all sizes."
                    }
                }
            ]
        },
        "cs": {
            "title": "O nás",
            "meta_description": "Zjistěte více o naší misi pomáhat organizacím dosáhnout připravenosti na audit",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "O naší platformě",
                        "subtitle": "Pomáhání organizacím dosáhnout připravenosti na audit",
                        "description": "Naše platforma poskytuje komplexní nástroje a pokyny, které organizacím pomáhají připravit se na audit a udržovat soulad."
                    }
                },
                {
                    "section_type": "standard",
                    "order": 2,
                    "data": {
                        "title": "Naše mise",
                        "content": "Jsme zavázáni zpřístupnit přípravu na audit pro organizace všech velikostí."
                    }
                }
            ]
        }
    },
    "contact": {
        "en": {
            "title": "Contact Us",
            "meta_description": "Get in touch with our team for support and inquiries",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Contact Us",
                        "subtitle": "We're here to help",
                        "description": "Have questions? Get in touch with our support team."
                    }
                }
            ]
        },
        "cs": {
            "title": "Kontaktujte nás",
            "meta_description": "Kontaktujte náš tým pro podporu a dotazy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Kontaktujte nás",
                        "subtitle": "Jsme zde pro vás",
                        "description": "Máte otázky? Kontaktujte náš support tým."
                    }
                }
            ]
        }
    },
    "faq": {
        "en": {
            "title": "Frequently Asked Questions",
            "meta_description": "Find answers to common questions about our platform",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Frequently Asked Questions",
                        "subtitle": "Find answers here",
                        "description": "Browse our FAQ section for common questions and answers."
                    }
                }
            ]
        },
        "cs": {
            "title": "Často kladené otázky",
            "meta_description": "Najděte odpovědi na běžné otázky o naší platformě",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Často kladené otázky",
                        "subtitle": "Najděte odpovědi zde",
                        "description": "Prohlédněte si naši FAQ sekci s běžnými otázkami a odpověďmi."
                    }
                }
            ]
        }
    },
    "products": {
        "en": {
            "title": "Products",
            "meta_description": "Explore our suite of audit readiness solutions",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Our Products",
                        "subtitle": "Complete Audit Readiness Solutions",
                        "description": "Discover our comprehensive product offerings designed to help your organization succeed."
                    }
                }
            ]
        },
        "cs": {
            "title": "Produkty",
            "meta_description": "Prozkoumejte naši sadu řešení pro připravenost na audit",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Naše produkty",
                        "subtitle": "Kompletní řešení pro připravenost na audit",
                        "description": "Objevte naši komplexní nabídku produktů navržených tak, aby vaší organizaci pomohly dosáhnout úspěchu."
                    }
                }
            ]
        }
    },
    "resources-public": {
        "en": {
            "title": "Resources",
            "meta_description": "Access helpful resources and guides for audit preparation",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Resources",
                        "subtitle": "Guides and Tools for Success",
                        "description": "Access our collection of resources to help you prepare for audits."
                    }
                }
            ]
        },
        "cs": {
            "title": "Zdroje",
            "meta_description": "Přístup k užitečným zdrojům a průvodcům přípravou auditu",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Zdroje",
                        "subtitle": "Průvodci a nástroje pro úspěch",
                        "description": "Přístup k naší kolekci zdrojů, které vám pomůžou připravit se na audity."
                    }
                }
            ]
        }
    },
    "privacy-policy": {
        "en": {
            "title": "Privacy Policy",
            "meta_description": "Read our privacy policy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Privacy Policy",
                        "content": "Your privacy is important to us. This privacy policy explains how we collect and use your information."
                    }
                }
            ]
        },
        "cs": {
            "title": "Zásady ochrany osobních údajů",
            "meta_description": "Přečtěte si naše zásady ochrany osobních údajů",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Zásady ochrany osobních údajů",
                        "content": "Vaše soukromí je pro nás důležité. Tyto zásady ochrany osobních údajů vysvětlují, jak shromažďujeme a používáme vaše informace."
                    }
                }
            ]
        }
    },
    "terms-of-service": {
        "en": {
            "title": "Terms of Service",
            "meta_description": "Read our terms of service",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Terms of Service",
                        "content": "By using our platform, you agree to these terms of service. Please read them carefully."
                    }
                }
            ]
        },
        "cs": {
            "title": "Podmínky služby",
            "meta_description": "Přečtěte si naše podmínky služby",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Podmínky služby",
                        "content": "Používáním naší platformy souhlasíte s těmito podmínkami služby. Přečtěte si je prosím pozorně."
                    }
                }
            ]
        }
    },
    "cookies": {
        "en": {
            "title": "Cookie Policy",
            "meta_description": "Learn about our cookie policy",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Cookie Policy",
                        "content": "We use cookies to enhance your experience. Learn more about how we use them."
                    }
                }
            ]
        },
        "cs": {
            "title": "Zásady cookies",
            "meta_description": "Zjistěte více o našich zásadách cookies",
            "status": "published",
            "content_type": "standard",
            "sections": [
                {
                    "section_type": "legal",
                    "order": 1,
                    "data": {
                        "title": "Zásady cookies",
                        "content": "Používáme cookies ke zlepšení vaší zkušenosti. Zjistěte více o tom, jak je používáme."
                    }
                }
            ]
        }
    },
}

def seed_database():
    """Seed the CMS database with initial content."""
    db: Session = SessionLocal()
    
    try:
        # Get admin user ID (first admin user in system)
        from app.models.user import User, UserRole
        admin_user = db.query(User).filter(User.role == UserRole.admin.value).first()
        
        if not admin_user:
            print("❌ Error: No admin user found in database")
            print("   Create an admin user first via the application signup/admin creation")
            return
        
        admin_id = admin_user.id
        print(f"✓ Using admin user: {admin_user.username or admin_user.email}")
        
        # Check if pages already exist
        existing_count = db.query(Page).count()
        if existing_count > 0:
            print(f"⚠ CMS already contains {existing_count} pages. Skipping seed.")
            return
        
        seeded = 0
        
        # Seed all pages
        for slug, languages in PAGES_DATA.items():
            for lang, page_data in languages.items():
                # Create page with proper UUID
                page = Page(
                    id=uuid4(),
                    slug=slug,
                    language=lang,
                    title=page_data["title"],
                    meta_description=page_data["meta_description"],
                    status=page_data["status"],
                    content_type=page_data["content_type"],
                    created_by_id=admin_id,
                    updated_by_id=admin_id,
                )
                db.add(page)
                db.flush()  # Get page ID
                
                # Add sections
                for section_data in page_data["sections"]:
                    section = PageSection(
                        id=uuid4(),
                        page_id=page.id,
                        section_type=section_data["section_type"],
                        order=section_data["order"],
                        data=section_data["data"],
                    )
                    db.add(section)
                
                seeded += 1
                print(f"✓ Seeded {slug} ({lang})")
        
        db.commit()
        print(f"\n✅ Successfully seeded {seeded} pages into CMS")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
