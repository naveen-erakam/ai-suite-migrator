# AI Suite Migrator

Migrate your complete Robot Framework test suite to Playwright (Python or JavaScript)
by uploading a ZIP file — no manual rewriting needed.

## How It Works

```
Upload Robot Framework ZIP
         ↓
AI reads every .robot file
         ↓
Converts test cases, keywords, variables, resources
         ↓
Downloads complete Playwright project ZIP
```

## Tech Stack

- **Streamlit** (web UI)
- **Groq API** (free — llama-3.3-70b)
- **Python** 3.11+

## Getting Started

```bash
pip install -r requirements.txt
cp .env.example .env
# Add your GROQ_API_KEY from console.groq.com

# Run the app
streamlit run webapp/streamlit_app.py
```

## What Gets Migrated

| Robot Framework | Playwright Output |
|---|---|
| *** Test Cases *** | pytest functions / test() blocks |
| *** Keywords *** | Page Object class methods |
| *** Variables *** | Python constants / JS config |
| *** Settings *** | imports + fixtures |
| [Tags] | pytest.mark / test.describe |
| SeleniumLibrary calls | Playwright API equivalents |

## Output Structure (Python example)

```
migrated_project/
├── README.md
├── requirements.txt
├── conftest.py           ← shared pytest fixtures
├── config/               ← migrated variables
├── pages/                ← migrated keywords → Page Objects
└── tests/                ← migrated test cases
```

## Large Projects

For 50+ file projects, migration runs in batches automatically
with delays between batches to respect API rate limits.
Estimated time: ~1-2 minutes per 10 files.

---
*Built and maintained by [Naveen Erakam](https://github.com/naveen-erakam)*
