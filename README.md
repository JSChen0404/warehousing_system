# warehousing_system

BD Warehousing System - A system for managing warehouse inventory, logistics and operations

## Quick Start

1. **Read CLAUDE.md first** - Contains essential rules for Claude Code
2. Install dependencies: `pip install -r requirements.txt`
3. Configure environment variables (copy `.env.example` to `.env`)
4. Initialize the database: `python init_db.py`
5. Run the application: `flask run`

## Project Structure

```
warehousing_system/
├── CLAUDE.md                   # Claude Code rules (read this first)
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── init_db.py                  # Database initialization script
├── .flaskenv                   # Flask environment configuration
├── warehousing_system/         # Main Flask application package
│   ├── __init__.py             # App factory
│   ├── models.py               # Database models
│   ├── routes.py               # Route handlers
│   ├── forms.py                # WTForms definitions
│   ├── static/                 # Static assets (CSS, JS, images)
│   └── templates/              # Jinja2 HTML templates
├── src/
│   ├── main/python/            # Additional Python modules
│   │   ├── core/               # Core business logic
│   │   ├── utils/              # Utility functions
│   │   ├── models/             # Additional data models
│   │   ├── services/           # Service layer
│   │   └── api/                # API endpoints
│   └── test/                   # Tests
│       ├── unit/               # Unit tests
│       └── integration/        # Integration tests
├── docs/                       # Documentation
├── output/                     # Generated output files
└── tools/                      # Development tools
```

## Tech Stack

- **Framework**: Flask
- **Database**: PostgreSQL (via SQLAlchemy)
- **Auth**: Flask-Security, MSAL
- **Forms**: WTForms / Flask-WTF

## Development Guidelines

- **Always search first** before creating new files
- **Extend existing** functionality rather than duplicating
- **Use Task agents** for operations >30 seconds
- **Single source of truth** for all functionality
- Commit after every completed task/feature
