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

# Page content data structure - comprehensive content from all frontend pages
PAGES_DATA = {
    "home": {
        "en": {
            "title": "Home",
            "meta_description": "AuditReady - Simplify your cybersecurity audit preparation",
            "status": "published",
            "content_type": "hero",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Be ready.",
                        "subtitle": "Stay confident.",
                        "description": "Practical tools that help you prepare for audits, close gaps, and prove security with confidence.",
                        "kicker": "Cybersecurity Simplified",
                        "background_image": "/assets/cybersecurity-background-59ognpsy7izka4l9.png",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "dashboard": {
                                "title": "Dashboard",
                                "metrics": {
                                    "overallReadiness": "Overall Readiness",
                                    "completed": "Completed",
                                    "openFindings": "Open Findings"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "How It Works",
                        "subtitle": "Get audit-ready in 3 simple steps",
                        "steps": [
                            {
                                "number": "1",
                                "title": "Assessment",
                                "description": "Complete comprehensive cybersecurity readiness assessment"
                            },
                            {
                                "number": "2", 
                                "title": "Analysis",
                                "description": "Get detailed analysis of your current security posture"
                            },
                            {
                                "number": "3",
                                "title": "Improvement",
                                "description": "Follow our guided recommendations to achieve audit readiness"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Trusted by Security Teams",
                        "badges": [
                            {
                                "name": "ISO 27001",
                                "description": "Compliant with international security standards"
                            },
                            {
                                "name": "SOC 2 Type II",
                                "description": "Certified for security controls and processes"
                            },
                            {
                                "name": "GDPR Ready",
                                "description": "Privacy and data protection compliant"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Start Your Audit Journey Today",
                        "subtitle": "Join security teams who trust AuditReady for their audit preparation needs",
                        "buttons": [
                            {
                                "text": "Get Started",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "View Demo",
                                "url": "/demo",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        },
        "cs": {
            "title": "Domů",
            "meta_description": "AuditReady - Zjednodušte si přípravu na kybernetický audit",
            "status": "published",
            "content_type": "hero",
            "sections": [
                {
                    "section_type": "hero",
                    "order": 1,
                    "data": {
                        "title": "Audit-Ready, Zjednodušeně.",
                        "subtitle": "kybernetická",
                        "accent": "bezpečnost.",
                        "description": "Transformujte přípravu na audit z chaosu do jasnosti. Naše komplexní platforma dává bezpečnostním týmům strukturu a sebedůvěru pro zvládnutí jakéhokoli kybernetického auditu.",
                        "kicker": "Profesionální příprava na audit",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklisty",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "dashboard": {
                                "title": "Dashboard",
                                "metrics": {
                                    "overallReadiness": "Celková připravenost",
                                    "completed": "Dokončeno",
                                    "openFindings": "Otevřená zjištění"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "Jak to funguje",
                        "subtitle": "Buďte připraveni na audit ve 3 jednoduchých krocích",
                        "steps": [
                            {
                                "number": "1",
                                "title": "Hodnocení",
                                "description": "Dokončete komplexní hodnocení připravenosti na kybernetickou bezpečnost"
                            },
                            {
                                "number": "2",
                                "title": "Analýza",
                                "description": "Získejte detailní analýzu vašeho současného bezpečnostního postavení"
                            },
                            {
                                "number": "3",
                                "title": "Zlepšení",
                                "description": "Následujte naše doporučení pro dosažení připravenosti na audit"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Důvěřují nám bezpečnostní týmy",
                        "badges": [
                            {
                                "name": "ISO 27001",
                                "description": "Splňuje mezinárodní bezpečnostní standardy"
                            },
                            {
                                "name": "SOC 2 Type II",
                                "description": "Certifikováno pro bezpečnostní kontroly a procesy"
                            },
                            {
                                "name": "GDPR Ready",
                                "description": "Splňuje požadavky na ochranu osobních údajů"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Začněte svou auditní cestu ještě dnes",
                        "subtitle": "Přidejte se k bezpečnostním týmům, které důvěřují AuditReady pro své potřeby přípravy na audit",
                        "buttons": [
                            {
                                "text": "Začít",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "Ukázka",
                                "url": "/demo",
                                "primary": False
                            }
                        ]
                    }
                }
            ]
        }
    },
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
                        "title": "Built by cybersecurity professionals",
                        "subtitle": "cybersecurity",
                        "accent": "professionals.",
                        "description": "We simplify audit preparation for today's cybersecurity challenges. Our mission is to give security and compliance teams clarity, structure, and confidence - without complexity.",
                        "kicker": "About Us",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklists": "Checklists",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "dashboard": {
                                "title": "Dashboard",
                                "metrics": {
                                    "overallReadiness": "Overall Readiness",
                                    "completed": "Completed",
                                    "openFindings": "Open Findings"
                                },
                                "activity": {
                                    "title": "Recent Activity",
                                    "items": [
                                        "Audit Readiness Checklist",
                                        "Documentation Package",
                                        "NIS2 Gap Analysis"
                                    ]
                                },
                                "domains": {
                                    "title": "Top Domains",
                                    "governance": "Governance",
                                    "risk": "Risk",
                                    "management": "Management",
                                    "access": "Access",
                                    "control": "Control",
                                    "asset": "Asset",
                                    "assetManagement": "Management",
                                    "incident": "Incident",
                                    "incidentManagement": "Management"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "What We Do",
                        "cards": [
                            {
                                "title": "What We Do",
                                "content": "We are cybersecurity professionals with hands-on experience in audits, compliance, and incident response. Over the years, we have worked with organizations across different industries, helping them strengthen their security and prepare for audits with confidence.",
                                "icon": "users"
                            },
                            {
                                "title": "Our Experience",
                                "points": [
                                    "Cybersecurity and audit expertise",
                                    "ISO 27001, NIS2, and relevant requirements under Czech Cybersecurity Act",
                                    "Security assessments and incident response",
                                    "Real-world experience across multiple industries"
                                ],
                                "icon": "check"
                            },
                            {
                                "title": "Why This Product Exists",
                                "content": "We saw that many organizations were unprepared not because of lack of effort, but because of unclear requirements, missing documentation, and lack of a structured approach. Existing tools were either too complex or not focused on what really matters during an audit.",
                                "highlight": "AuditReady was created to change that.",
                                "icon": "lightbulb"
                            },
                            {
                                "title": "Our Approach",
                                "content": "We believe audit preparation should be practical, clear, and evidence-based. That's why we built a solution that focuses on what really matters and guides you step by step.",
                                "points": [
                                    "Practical, not theoretical",
                                    "Focused on real audit readiness",
                                    "Evidence-based approach",
                                    "Simple and structured workflow"
                                ],
                                "icon": "target"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Trust & Credentials",
                        "subtitle": "We combine real-world experience with recognized knowledge and standards.",
                        "cards": [
                            {
                                "title": "Real-World Experience",
                                "content": "Years of hands-on work with audits, security assessments, and incident response.",
                                "icon": "document"
                            },
                            {
                                "title": "Certifications",
                                "content": "Industry-recognized certifications including CISSP, CySA+, and ISO 27001 Lead Auditor.",
                                "icon": "graduation"
                            },
                            {
                                "title": "Security Standards",
                                "content": "Deep knowledge of frameworks such as NIS2, ISO 27001, and other international standards.",
                                "icon": "shield"
                            },
                            {
                                "title": "Practical Partnerships",
                                "content": "Collaboration with organizations to strengthen their security and achieve compliance goals.",
                                "icon": "handshake"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Want to know more about our work?",
                        "subtitle": "We're always open to new conversations about how we can help you and your organization stay secure and audit-ready.",
                        "buttons": [
                            {
                                "text": "Contact Us",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Explore Products",
                                "url": "/products",
                                "primary": False
                            }
                        ]
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
                        "title": "Vytvořeno",
                        "subtitle": "odborníky na",
                        "accent": "kybernetickou bezpečnost.",
                        "description": "Pomáháme organizacím rychle zjistit, co je skutečně připravené na audit a co zatím chybí. AuditReady přináší bezpečnostním a compliance týmům přehled, strukturu a jistotu v tom, co lze doložit, kde jsou mezery a na co se zaměřit před dalším auditem.",
                        "kicker": "O nás",
                        "mockup": {
                            "brand": "AuditReady",
                            "nav": {
                                "dashboard": "Přehled",
                                "checklists": "Checklisty",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "dashboard": {
                                "title": "Přehled",
                                "metrics": {
                                    "overallReadiness": "Celková připravenost",
                                    "completed": "Dokončeno",
                                    "openFindings": "Otevřená zjištění"
                                },
                                "activity": {
                                    "title": "Poslední aktivita",
                                    "items": [
                                        "Audit Readiness Checklist",
                                        "Balíček dokumentace",
                                        "NIS2 gap analýza"
                                    ]
                                },
                                "domains": {
                                    "title": "Klíčové oblasti",
                                    "governance": "Governance",
                                    "risk": "Řízení",
                                    "management": "rizik",
                                    "access": "Řízení",
                                    "control": "přístupu",
                                    "asset": "Správa",
                                    "assetManagement": "aktiv",
                                    "incident": "Řízení",
                                    "incidentManagement": "incidentů"
                                }
                            }
                        }
                    }
                },
                {
                    "section_type": "cards",
                    "order": 2,
                    "data": {
                        "title": "Co děláme",
                        "cards": [
                            {
                                "title": "Co děláme",
                                "content": "Pomáháme organizacím zhodnotit, v jakém stavu je jejich kybernetická bezpečnost a co je v praxi skutečně připravené. Vycházíme ze zkušeností z auditů a řízení bezpečnosti napříč různými organizacemi a zaměřujeme se na to, co dává smysl v reálném provozu. Soustředíme se na to, aby bezpečnost nebyla jen deklarovaná, ale také skutečně doložitelná.",
                                "icon": "users"
                            },
                            {
                                "title": "Naše zkušenosti",
                                "points": [
                                    "Odbornost v oblasti kybernetické bezpečnosti a auditní přípravy",
                                    "Praktická zkušenost s požadavky zákona o kybernetické bezpečnosti a navazujících vyhlášek",
                                    "Znalost rámců a standardů, jako jsou ISO 27001 a NIST",
                                    "Praxe z veřejného i soukromého sektoru"
                                ],
                                "icon": "check"
                            },
                            {
                                "title": "Proč to děláme",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit.",
                                "highlight": "AuditReady vzniklo proto, aby to celé bylo jednodušší a srozumitelné.",
                                "icon": "lightbulb"
                            },
                            {
                                "title": "Jak pracujeme",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti.",
                                "points": [
                                    "Prakticky, ne teoreticky",
                                    "Zaměřeno na skutečnou auditní připravenost",
                                    "Doložitelnost a evidence",
                                    "Jednoduchý a strukturovaný postup"
                                ],
                                "icon": "target"
                            }
                        ]
                    }
                },
                {
                    "section_type": "trust",
                    "order": 3,
                    "data": {
                        "title": "Proč nám můžete věřit",
                        "subtitle": "Stavíme na praktických zkušenostech, odborných znalostech a ověřených standardech.",
                        "cards": [
                            {
                                "title": "Zkušenosti z praxe",
                                "content": "Pomáháme oddělit formální deklarace od skutečného stavu a ukázat, co organizace dokáže při kontrole doložit.",
                                "icon": "document"
                            },
                            {
                                "title": "Certifikace",
                                "content": "Disponujeme odbornými certifikacemi v oblasti kybernetické bezpečnosti a auditu, včetně CISSP, CISA a ISO 27001 Lead Auditor.",
                                "icon": "graduation"
                            },
                            {
                                "title": "Standardy a metodiky",
                                "content": "Opíráme se o ISO 27001, NIST frameworky, ITIL, TOGAF a další osvědčené přístupy pro řízení bezpečnosti, IT služeb a architektury.",
                                "icon": "shield"
                            },
                            {
                                "title": "Spolupráce s organizacemi",
                                "content": "Pomáháme organizacím zlepšovat bezpečnost a připravit se na audit bez zbytečné složitosti.",
                                "icon": "handshake"
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 4,
                    "data": {
                        "title": "Chcete vědět víc o tom, jak pracujeme?",
                        "subtitle": "Jsme připraveni probrat, jak můžeme vaší organizaci pomoci lépe vyhodnotit stav kybernetické bezpečnosti a podpořit přípravu na audit nebo interní kontrolu.",
                        "buttons": [
                            {
                                "text": "Kontaktujte nás",
                                "url": "/contact",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products",
                                "primary": False
                            }
                        ]
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
                        "subtitle": "Have a question about audit readiness or product?",
                        "kicker": "Contact Us",
                        "form": {
                            "name": "Name",
                            "email": "Email",
                            "company": "Company (optional)",
                            "message": "Message",
                            "messagePlaceholder": "Describe your situation (e.g., upcoming audit, missing documentation, unclear requirements)",
                            "sendButton": "Send Message"
                        },
                        "directContact": {
                            "title": "Prefer direct contact?",
                            "subtitle": "Feel free to email us anytime.",
                            "email": "info@checklistkb.com",
                            "responseTime": "We respond within 24 hours."
                        }
                    }
                },
                {
                    "section_type": "cta",
                    "order": 2,
                    "data": {
                        "title": "Start your assessment today",
                        "subtitle": "Get access to our tools and simplify your cybersecurity audit process.",
                        "buttons": [
                            {
                                "text": "Get Access",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "View Products",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
                    }
                },
                {
                    "section_type": "bottom-cta",
                    "order": 3,
                    "data": {
                        "title": "Start your assessment today",
                        "subtitle": "Sign up now and simplify your cybersecurity audit process.",
                        "buttons": [
                            {
                                "text": "Get Access",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "View Products",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
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
                        "subtitle": "Máte dotaz k auditní připravenosti nebo k produktu?",
                        "kicker": "Kontaktujte nás",
                        "form": {
                            "name": "Jméno",
                            "email": "E-mail",
                            "company": "Společnost (volitelné)",
                            "message": "Zpráva",
                            "messagePlaceholder": "Popište svou situaci (např. blížící se audit, chybějící dokumentace, nejasné požadavky)",
                            "sendButton": "Odeslat zprávu"
                        },
                        "directContact": {
                            "title": "Preferujete přímý kontakt?",
                            "subtitle": "Napište nám kdykoliv e-mailem.",
                            "email": "info@checklistkb.com",
                            "responseTime": "Odpovídáme do 24 hodin."
                        }
                    }
                },
                {
                    "section_type": "cta",
                    "order": 2,
                    "data": {
                        "title": "Začněte s hodnocením ještě dnes",
                        "subtitle": "Získejte přístup k našim nástrojům a zjednodušte audit kybernetické bezpečnosti.",
                        "buttons": [
                            {
                                "text": "Získat přístup",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
                    }
                },
                {
                    "section_type": "bottom-cta",
                    "order": 3,
                    "data": {
                        "title": "Začněte s hodnocením ještě dnes",
                        "subtitle": "Zaregistrujte se a zjednodušte audit kybernetické bezpečnosti.",
                        "buttons": [
                            {
                                "text": "Získat přístup",
                                "url": "/register",
                                "primary": True
                            },
                            {
                                "text": "Zobrazit produkty",
                                "url": "/products/audit-readiness-checklist",
                                "primary": False
                            }
                        ]
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
                        "subtitle": "Everything you need to know about access, assessments, reports, and platform security.",
                        "kicker": "Help center"
                    }
                },
                {
                    "section_type": "faq",
                    "order": 2,
                    "data": {
                        "title": "Quick Answers",
                        "subtitle": "Click a question to expand details.",
                        "questions": [
                            {
                                "question": "When does my 7-day window begin?",
                                "answer": "The 7-day completion window starts only when you click Start Assessment, not immediately after payment."
                            },
                            {
                                "question": "Is evidence upload mandatory?",
                                "answer": "No. Uploads are optional, but recommended to support auditor review and report quality."
                            },
                            {
                                "question": "How is access unlocked after payment?",
                                "answer": "Access is unlocked automatically after Stripe webhook confirmation is processed by backend."
                            },
                            {
                                "question": "Which roles are supported?",
                                "answer": "The platform supports admin/operator, read-only auditor, and customer roles."
                            },
                            {
                                "question": "Can I save progress and continue later?",
                                "answer": "Yes. Your assessment progress is saved so you can continue within your active access window."
                            },
                            {
                                "question": "How do I get my final report?",
                                "answer": "After completing checklist, your report is available in Reports area for download and sharing."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 3,
                    "data": {
                        "title": "Still have questions?",
                        "subtitle": "Reach out and we'll help you get answers you need.",
                        "button": {
                            "text": "Contact Us",
                            "url": "/contact"
                        }
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
                        "subtitle": "Vše, co potřebujete vědět o přístupu, hodnocení, reportech a bezpečnosti platformy.",
                        "kicker": "Centrum nápovědy"
                    }
                },
                {
                    "section_type": "faq",
                    "order": 2,
                    "data": {
                        "title": "Rychlé odpovědi",
                        "subtitle": "Kliknutím na otázku zobrazíte detail.",
                        "questions": [
                            {
                                "question": "Kdy začíná 7denní období?",
                                "answer": "Sedmidenní okno začíná až ve chvíli, kdy kliknete na 'Start Assessment', ne hned po platbě."
                            },
                            {
                                "question": "Je nahrání důkazů povinné?",
                                "answer": "Ne. Nahrávání je volitelné, ale doporučené pro podporu auditorova ověření a kvality reportu."
                            },
                            {
                                "question": "Jak se po zaplacení odemkne přístup?",
                                "answer": "Přístup se odemkne automaticky po zpracování potvrzení webhooks ze Stripe na backendu."
                            },
                            {
                                "question": "Jaké role jsou podporované?",
                                "answer": "Platforma podporuje role admin/operator, auditor pouze pro čtení a zákaznické role."
                            },
                            {
                                "question": "Mohu si uložit postup a pokračovat později?",
                                "answer": "Ano. Průběh hodnocení se ukládá, takže můžete pokračovat v rámci aktivního přístupového okna."
                            },
                            {
                                "question": "Jak získám finální report?",
                                "answer": "Po dokončení checklistu je report dostupný v části Reports pro stažení a sdílení."
                            }
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 3,
                    "data": {
                        "title": "Máte další otázky?",
                        "subtitle": "Napište nám a pomůžeme vám získat odpovědi, které potřebujete.",
                        "button": {
                            "text": "Kontaktujte nás",
                            "url": "/contact"
                        }
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
                        "title": "Close Gaps. Save Time.",
                        "subtitle": "Get Expert-Ready",
                        "accent": "Documentation.",
                        "description": "Buy individual policy sections with ready-to-use templates, guidelines, and admin instructions - written by security experts, aligned to ISO 27001, NIS2, and best practices.",
                        "kicker": "Documentation blueprints",
                        "highlights": [
                            {
                                "title": "Audit-ready",
                                "body": "Aligned to frameworks"
                            },
                            {
                                "title": "Instant delivery",
                                "body": "Download and use"
                            },
                            {
                                "title": "Expert written",
                                "body": "Practical. Clear. Complete."
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "library": "Documentation Library",
                            "nav": {
                                "dashboard": "Dashboard",
                                "checklist": "Checklist",
                                "evidence": "Evidence",
                                "reports": "Reports",
                                "settings": "Settings"
                            },
                            "documents": [
                                "Mobile Device Policy",
                                "Access Control Policy",
                                "Incident Response Policy",
                                "Data Classification Policy"
                            ]
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "How it works",
                        "subtitle": "Find section you need. Download. Customize. Stay compliant.",
                        "steps": [
                            {
                                "title": "1. Find Gap",
                                "body": "Your assessment shows what's missing."
                            },
                            {
                                "title": "2. Choose a Section",
                                "body": "Pick policy section you need."
                            },
                            {
                                "title": "3. Download Instantly",
                                "body": "Get documents in PDF and DOCX."
                            },
                            {
                                "title": "4. Customize & Use",
                                "body": "Adapt to your organization. You're ready."
                            }
                        ]
                    }
                },
                {
                    "section_type": "documentation-grid",
                    "order": 3,
                    "data": {
                        "title": "Browse Documentation Sections",
                        "subtitle": "Each section includes a policy, user guidelines, and admin guidelines.",
                        "categories": [
                            "All",
                            "Access & Identity",
                            "Devices & Endpoints",
                            "Data Protection",
                            "Operations",
                            "Governance",
                            "Response"
                        ],
                        "documents": [
                            {
                                "id": "mobileDevice",
                                "name": "Mobile Device Policy",
                                "subtitle": "Define rules for corporate and personal mobile devices.",
                                "price": "€149",
                                "category": "Devices & Endpoints",
                                "badge": "Popular",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "remoteWork",
                                "name": "Remote Work Policy",
                                "subtitle": "Secure and productive remote work, clearly defined.",
                                "price": "€149",
                                "category": "Operations",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "accessControl",
                                "name": "Access Control Policy",
                                "subtitle": "Manage who has access to what, and under which conditions.",
                                "price": "€179",
                                "category": "Access & Identity",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines",
                                    "Admin Guidelines (Advanced)"
                                ]
                            },
                            {
                                "id": "incidentResponse",
                                "name": "Incident Response Policy",
                                "subtitle": "Be ready when incidents happen. Act fast. Act right.",
                                "price": "€199",
                                "category": "Response",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines",
                                    "Response Playbooks"
                                ]
                            },
                            {
                                "id": "dataClassification",
                                "name": "Data Classification Policy",
                                "subtitle": "Define how data is labeled, handled, and protected.",
                                "price": "€149",
                                "category": "Data Protection",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            },
                            {
                                "id": "securityGovernance",
                                "name": "Security Governance Policy",
                                "subtitle": "Roles, accountability, and oversight for your information security program.",
                                "price": "€189",
                                "category": "Governance",
                                "points": [
                                    "Policy Document",
                                    "User Guidelines",
                                    "Admin Guidelines"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "bundles",
                    "order": 4,
                    "data": {
                        "title": "Bundle & Save",
                        "subtitle": "Get multiple sections and save up to 25%.",
                        "bundles": [
                            {
                                "title": "Essential Bundle",
                                "subtitle": "3 sections of your choice",
                                "price": "€399",
                                "originalPrice": "€447",
                                "save": "Save 10%"
                            },
                            {
                                "title": "Professional Bundle",
                                "subtitle": "5 sections of your choice",
                                "price": "€599",
                                "originalPrice": "€745",
                                "save": "Save 20%",
                                "badge": "Most Popular"
                            },
                            {
                                "title": "Complete Bundle",
                                "subtitle": "10 sections of your choice",
                                "price": "€999",
                                "originalPrice": "€1,490",
                                "save": "Save 25%"
                            }
                        ]
                    }
                },
                {
                    "section_type": "why-choose",
                    "order": 5,
                    "data": {
                        "title": "Why organizations choose our documentation",
                        "points": [
                            "Written by cybersecurity experts",
                            "Aligned to ISO 27001, NIS2 and best practices",
                            "Ready to customize and use",
                            "Saves weeks of manual work",
                            "Used by auditors and security teams"
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 6,
                    "data": {
                        "title": "Found a gap. Now close it.",
                        "subtitle": "Get right documentation section and move forward with confidence.",
                        "buttons": [
                            {
                                "text": "View product details",
                                "url": "/products/audit-readiness-checklist"
                            },
                            {
                                "text": "Create account",
                                "url": "/register"
                            }
                        ]
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
                        "title": "Uzavřete mezery. Ušetřete čas.",
                        "subtitle": "Získejte dokumentaci",
                        "accent": "připravenou pro audit.",
                        "description": "Kupte jednotlivé části zásad s připravenými šablonami, doporučeními a admin instrukcemi – napsané bezpečnostními experty, sladěné s ISO 27001, NIS2 a best practices.",
                        "kicker": "Dokumentační šablony",
                        "highlights": [
                            {
                                "title": "Audit-ready",
                                "body": "Sladěno s rámci"
                            },
                            {
                                "title": "Okamžité doručení",
                                "body": "Stáhněte a použijte"
                            },
                            {
                                "title": "Napsané experty",
                                "body": "Praktické. Jasné. Kompletní."
                            }
                        ],
                        "mockup": {
                            "brand": "AuditReady",
                            "library": "Knihovna dokumentace",
                            "nav": {
                                "dashboard": "Přehled",
                                "checklist": "Checklist",
                                "evidence": "Důkazy",
                                "reports": "Reporty",
                                "settings": "Nastavení"
                            },
                            "documents": [
                                "Zásada pro mobilní zařízení",
                                "Zásada řízení přístupu",
                                "Postup reakce na incidenty",
                                "Zásada klasifikace dat"
                            ]
                        }
                    }
                },
                {
                    "section_type": "how-it-works",
                    "order": 2,
                    "data": {
                        "title": "Jak to funguje",
                        "subtitle": "Najděte potřebnou část. Stáhněte. Upravte. Buďte v souladu.",
                        "steps": [
                            {
                                "title": "1. Najděte mezeru",
                                "body": "Hodnocení ukáže, co chybí."
                            },
                            {
                                "title": "2. Vyberte sekci",
                                "body": "Zvolte část zásady, kterou potřebujete."
                            },
                            {
                                "title": "3. Okamžitě stáhněte",
                                "body": "Získejte dokumenty v PDF a DOCX."
                            },
                            {
                                "title": "4. Upravte a používejte",
                                "body": "Přizpůsobte organizaci. Hotovo."
                            }
                        ]
                    }
                },
                {
                    "section_type": "documentation-grid",
                    "order": 3,
                    "data": {
                        "title": "Procházet sekce dokumentace",
                        "subtitle": "Každá sekce obsahuje zásadu, uživatelské a admin pokyny.",
                        "categories": [
                            "Vše",
                            "Přístup & identita",
                            "Zařízení & endpointy",
                            "Ochrana dat",
                            "Provoz",
                            "Governance",
                            "Reakce"
                        ],
                        "documents": [
                            {
                                "id": "mobileDevice",
                                "name": "Zásada pro mobilní zařízení",
                                "subtitle": "Definuje pravidla pro firemní i soukromá mobilní zařízení.",
                                "price": "€149",
                                "category": "Zařízení & endpointy",
                                "badge": "Oblíbené",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "remoteWork",
                                "name": "Zásada práce na dálku",
                                "subtitle": "Bezpečná a produktivní práce na dálku – jasně definovaná.",
                                "price": "€149",
                                "category": "Provoz",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "accessControl",
                                "name": "Zásada řízení přístupu",
                                "subtitle": "Řiďte, kdo má k čemu přístup a za jakých podmínek.",
                                "price": "€179",
                                "category": "Přístup & identita",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory",
                                    "Pokyny pro administrátory (pokročilé)"
                                ]
                            },
                            {
                                "id": "incidentResponse",
                                "name": "Postup reakce na incidenty",
                                "subtitle": "Buďte připraveni na incidenty. Rychle. Správně.",
                                "price": "€199",
                                "category": "Reakce",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory",
                                    "Incidentní scénáře"
                                ]
                            },
                            {
                                "id": "dataClassification",
                                "name": "Zásada klasifikace dat",
                                "subtitle": "Definuje, jak jsou data označována, zpracovávána a chráněna.",
                                "price": "€149",
                                "category": "Ochrana dat",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            },
                            {
                                "id": "securityGovernance",
                                "name": "Zásada řízení bezpečnosti",
                                "subtitle": "Role, odpovědnosti a dohled nad programem informační bezpečnosti.",
                                "price": "€189",
                                "category": "Governance",
                                "points": [
                                    "Dokument zásady",
                                    "Pokyny pro uživatele",
                                    "Pokyny pro administrátory"
                                ]
                            }
                        ]
                    }
                },
                {
                    "section_type": "bundles",
                    "order": 4,
                    "data": {
                        "title": "Balíčky & úspora",
                        "subtitle": "Získejte více sekcí a ušetřete až 25 %.",
                        "bundles": [
                            {
                                "title": "Essential balíček",
                                "subtitle": "3 sekce dle výběru",
                                "price": "€399",
                                "originalPrice": "€447",
                                "save": "Ušetříte 10 %"
                            },
                            {
                                "title": "Professional balíček",
                                "subtitle": "5 sekcí dle výběru",
                                "price": "€599",
                                "originalPrice": "€745",
                                "save": "Ušetříte 20 %",
                                "badge": "Nejoblíbenější"
                            },
                            {
                                "title": "Complete balíček",
                                "subtitle": "10 sekcí dle výběru",
                                "price": "€999",
                                "originalPrice": "€1,490",
                                "save": "Ušetříte 25 %"
                            }
                        ]
                    }
                },
                {
                    "section_type": "why-choose",
                    "order": 5,
                    "data": {
                        "title": "Proč si organizace vybírají naši dokumentaci",
                        "points": [
                            "Napsáno odborníky na kybernetickou bezpečnost",
                            "Sladěno s ISO 27001, NIS2 a best practices",
                            "Připravené k úpravě a okamžitému použití",
                            "Ušetří týdny manuální práce",
                            "Používané auditory i bezpečnostními týmy"
                        ]
                    }
                },
                {
                    "section_type": "cta",
                    "order": 6,
                    "data": {
                        "title": "Našli jste mezeru. Teď ji uzavřete.",
                        "subtitle": "Vyberte správnou část dokumentace a posuňte se dál s jistotou.",
                        "buttons": [
                            {
                                "text": "Zobrazit detail produktu",
                                "url": "/products/audit-readiness-checklist"
                            },
                            {
                                "text": "Vytvořit účet",
                                "url": "/register"
                            }
                        ]
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
                        "description": "Access our collection of resources to help you prepare for audits.",
                        "kicker": "Resources"
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
                        "description": "Přístup k naší kolekci zdrojů, které vám pomůžou připravit se na audity.",
                        "kicker": "Zdroje"
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
                        "content": "Your privacy is important to us. This privacy policy explains how we collect and use your information. We are committed to protecting your personal data and ensuring transparency in our data practices."
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
                        "content": "Vaše soukromí je pro nás důležité. Tyto zásady ochrany osobních údajů vysvětlují, jak shromažďujeme a používáme vaše informace. Jsme zavázáni chránit vaše osobní údaje a zajistit transparentnost v našich datových postupech."
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
                        "content": "By using our platform, you agree to these terms of service. Please read them carefully. These terms govern your use of our audit readiness platform and outline the responsibilities of both parties."
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
                        "content": "Používáním naší platformy souhlasíte s těmito podmínkami služby. Přečtěte si je prosím pozorně. Tyto podmínky upravují vaše používání naší platformy pro připravenost na audit a definují odpovědnosti obou stran."
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
                        "content": "We use cookies to enhance your experience. Learn more about how we use them. Cookies help us analyze traffic, personalize content, and improve our services to better meet your needs."
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
                        "content": "Používáme cookies ke zlepšení vaší zkušenosti. Zjistěte více o tom, jak je používáme. Cookies nám pomáhají analyzovat provoz, personalizovat obsah a zlepšovat naše služby, aby lépe vyhovovaly vašim potřebám."
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
