import os
import re
import json
import zipfile
import time
from pathlib import Path
from io import BytesIO
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from groq import Groq

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# For large projects — process in batches to avoid rate limits
BATCH_SIZE  = 5   # files per batch
BATCH_DELAY = 8   # seconds between batches


def load_prompt(stack: str) -> str:
    prompt_map = {
        "Playwright + Python":     "playwright_python_prompt.txt",
        "Playwright + JavaScript": "playwright_js_prompt.txt",
    }
    with open(PROMPTS_DIR / prompt_map[stack], "r") as f:
        return f.read()


def extract_robot_files(zip_file) -> dict:
    """Extract all .robot files from ZIP, preserving folder structure."""
    robot_files = {}
    with zipfile.ZipFile(zip_file, "r") as zf:
        for name in zf.namelist():
            if name.endswith(".robot") and not name.endswith("/"):
                content = zf.read(name).decode("utf-8", errors="ignore")
                robot_files[name] = content
    return robot_files


def classify_file(content: str) -> str:
    """Classify .robot file type."""
    has_tests    = "*** Test Cases ***"    in content
    has_keywords = "*** Keywords ***"     in content
    has_vars     = "*** Variables ***"    in content

    if has_tests:
        return "test_suite"
    elif has_keywords:
        return "resource"
    elif has_vars:
        return "variables"
    else:
        return "config"


def get_output_path(original_path: str, stack: str, file_type: str) -> str:
    """Map .robot path → target framework path keeping folder hierarchy."""
    ext   = ".py" if "Python" in stack else ".js"
    parts = Path(original_path).parts
    # Strip top-level project folder name
    parts = parts[1:] if len(parts) > 1 else parts
    stem  = Path(parts[-1]).stem.lower().replace(" ", "_")
    dirs  = parts[:-1]

    if file_type == "test_suite":
        folder = ("tests",) + dirs
        name   = f"test_{stem}{ext}"
    elif file_type == "resource":
        folder = ("pages",) + dirs
        name   = f"{stem}_page{ext}"
    elif file_type == "variables":
        folder = ("config",) + dirs
        name   = f"config_{stem}{ext}"
    else:
        folder = ("utils",) + dirs
        name   = f"{stem}{ext}"

    return str(Path(*folder) / name)


def migrate_single_file(path: str, content: str, file_type: str,
                        stack: str, client: Groq,
                        retry: int = 3) -> tuple:
    """Migrate one file with retry logic. Returns (output_path, code, status)."""
    system_prompt = load_prompt(stack)
    output_path   = get_output_path(path, stack, file_type)

    user_msg = f"""Migrate this Robot Framework {file_type} file to {stack}.

File: {path}

--- CONTENT ---
{content}
--- END ---"""

    for attempt in range(retry):
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_msg}
                ],
                temperature=0.1,
                max_tokens=3000,
            )

            code = response.choices[0].message.content.strip()

            # Strip markdown fences
            if "```" in code:
                parts = code.split("```")
                code  = parts[1] if len(parts) > 1 else code
                for lang in ("python", "javascript", "js", "py", "robot"):
                    if code.lower().startswith(lang):
                        code = code[code.index("\n")+1:]
                        break

            return output_path, code.strip(), "success"

        except Exception as e:
            err = str(e)
            if "rate_limit" in err.lower() or "quota" in err.lower():
                wait = 30 * (attempt + 1)
                time.sleep(wait)
            elif attempt == retry - 1:
                # Return a stub file on final failure
                ext  = ".py" if "Python" in stack else ".js"
                stub = (
                    f"# ⚠️ Migration failed for: {path}\n"
                    f"# Error: {err}\n"
                    f"# Please migrate this file manually.\n\n"
                    f"# Original content:\n"
                    + "\n".join(f"# {l}" for l in content.split("\n"))
                )
                return output_path, stub, "failed"
            else:
                time.sleep(5)

    return output_path, f"# Migration failed: {path}", "failed"


def generate_project_config(stack: str, project_name: str) -> dict:
    configs = {}

    if "Python" in stack:
        configs["requirements.txt"] = (
            "playwright==1.43.0\n"
            "pytest==8.2.0\n"
            "pytest-playwright==0.5.0\n"
            "python-dotenv==1.0.1\n"
        )
        configs["conftest.py"] = (
            '"""Pytest configuration — migrated from Robot Framework."""\n'
            "import pytest\n"
            "from playwright.sync_api import sync_playwright\n\n"
            "BASE_URL = \"https://your-app-url.com\"\n\n\n"
            "@pytest.fixture(scope=\"session\")\n"
            "def browser_instance():\n"
            "    with sync_playwright() as p:\n"
            "        browser = p.chromium.launch(headless=False)\n"
            "        yield browser\n"
            "        browser.close()\n\n\n"
            "@pytest.fixture(scope=\"function\")\n"
            "def page(browser_instance):\n"
            "    context = browser_instance.new_context()\n"
            "    page = context.new_page()\n"
            "    yield page\n"
            "    context.close()\n"
        )
        configs["README.md"] = (
            f"# {project_name} — Playwright (Python)\n\n"
            "Migrated from Robot Framework by **AI Suite Migrator**.\n\n"
            "## Setup\n```bash\npip install -r requirements.txt\n"
            "playwright install chromium\n```\n\n"
            "## Run\n```bash\npytest tests/ -v\n```\n\n"
            "> **Review locators** in `pages/` and update `BASE_URL` in `conftest.py` before running.\n"
        )
    else:
        configs["package.json"] = json.dumps({
            "name": project_name.lower().replace(" ", "-"),
            "version": "1.0.0",
            "scripts": {
                "test":        "npx playwright test",
                "test:headed": "npx playwright test --headed",
                "test:report": "npx playwright show-report"
            },
            "devDependencies": {"@playwright/test": "^1.43.0"}
        }, indent=2)

        configs["playwright.config.js"] = (
            "const { defineConfig } = require('@playwright/test');\n\n"
            "module.exports = defineConfig({\n"
            "  testDir: './tests',\n"
            "  timeout: 30000,\n"
            "  retries: 1,\n"
            "  use: {\n"
            "    baseURL: 'https://your-app-url.com',\n"
            "    headless: false,\n"
            "    screenshot: 'only-on-failure',\n"
            "  },\n"
            "  reporter: [['html'], ['list']],\n"
            "});\n"
        )
        configs["README.md"] = (
            f"# {project_name} — Playwright (JavaScript)\n\n"
            "Migrated from Robot Framework by **AI Suite Migrator**.\n\n"
            "## Setup\n```bash\nnpm install\nnpx playwright install\n```\n\n"
            "## Run\n```bash\nnpm test\n```\n\n"
            "> **Review locators** in `pages/` and update `baseURL` in `playwright.config.js` before running.\n"
        )

    return configs


def migrate_suite(zip_file, stack: str, project_name: str,
                  progress_callback=None) -> tuple:
    """
    Main migration function.
    Returns (zip_buffer: BytesIO, summary: dict)
    """
    client      = Groq(api_key=os.environ.get("GROQ_API_KEY"))
    robot_files = extract_robot_files(zip_file)

    if not robot_files:
        raise ValueError("No .robot files found in the uploaded ZIP.")

    # Sort: variables & resources first (they're dependencies)
    def sort_key(item):
        path, content = item
        t = classify_file(content)
        order = {"variables": 0, "resource": 1, "config": 2, "test_suite": 3}
        return order.get(t, 4)

    sorted_files = sorted(robot_files.items(), key=sort_key)
    total        = len(sorted_files)

    output       = BytesIO()
    log          = []
    success_count= 0
    fail_count   = 0

    # Split into batches for large projects
    batches = [sorted_files[i:i+BATCH_SIZE]
               for i in range(0, total, BATCH_SIZE)]

    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as zf:
        # Add framework boilerplate files
        for cfg_name, cfg_content in generate_project_config(stack, project_name).items():
            zf.writestr(cfg_name, cfg_content)

        processed = 0
        for batch_idx, batch in enumerate(batches):

            # Delay between batches to respect rate limits
            if batch_idx > 0:
                time.sleep(BATCH_DELAY)

            for path, content in batch:
                file_type   = classify_file(content)
                output_path, code, status = migrate_single_file(
                    path, content, file_type, stack, client
                )

                zf.writestr(output_path, code)
                processed += 1

                if status == "success":
                    success_count += 1
                else:
                    fail_count    += 1

                log.append({
                    "original": path,
                    "migrated": output_path,
                    "type":     file_type,
                    "status":   status
                })

                if progress_callback:
                    progress_callback(processed, total, path, output_path, status)

        # Migration log
        summary = {
            "project":       project_name,
            "stack":         stack,
            "timestamp":     datetime.now().isoformat(),
            "total_files":   total,
            "success_count": success_count,
            "fail_count":    fail_count,
            "files":         log
        }
        zf.writestr("MIGRATION_LOG.json", json.dumps(summary, indent=2))

    output.seek(0)
    return output, summary
