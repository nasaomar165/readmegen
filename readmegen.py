#!/usr/bin/env python3
"""
readmegen - AI-powered README generator for any code repository.

Supported providers:
  Cloud (free tiers): Groq, Google Gemini, DeepSeek, Kimi (Moonshot), GLM (Zhipu)
  Local:              Ollama, LM Studio

Usage:
  python readmegen.py [path] [options]
"""

import os
import sys
import argparse
import json
import urllib.request
import urllib.error
import urllib.parse
import ssl
from pathlib import Path

# ─── Version ──────────────────────────────────────────────────────────────────

__version__ = "0.2.1"

# ─── ASCII Art Banner ─────────────────────────────────────────────────────────
BANNER = f"""
╔══════════════════════════════════════════════════════════════════════════════════╗
║                                                                                  ║
║  ██████╗ ███████╗ █████╗ ██████╗ ███╗   ███╗███████╗ ██████╗ ███████╗███╗   ██╗  ║
║  ██╔══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝██╔════╝ ██╔════╝████╗  ██║  ║
║  ██████╔╝█████╗  ███████║██║  ██║██╔████╔██║█████╗  ██║  ███╗█████╗  ██╔██╗ ██║  ║
║  ██╔══██╗██╔══╝  ██╔══██║██║  ██║██║╚██╔╝██║██╔══╝  ██║   ██║██╔══╝  ██║╚██╗██║  ║
║  ██║  ██║███████╗██║  ██║██████╔╝██║ ╚═╝ ██║███████╗╚██████╔╝███████╗██║ ╚████║  ║
║  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝  ║
║                                                                                  ║
║                        >> readmegen - README.md automation <<                    ║
║                                version {__version__}                                     ║
╚══════════════════════════════════════════════════════════════════════════════════╝
"""

# ─── Config ───────────────────────────────────────────────────────────────────

IGNORE_DIRS = {
    ".git", ".svn", "node_modules", "__pycache__", ".venv", "venv", "env",
    ".env", "dist", "build", ".next", ".nuxt", "coverage", ".pytest_cache",
    ".mypy_cache", ".tox", "eggs", ".eggs", "*.egg-info", ".idea", ".vscode",
    "target", "out", "bin", "obj", ".gradle", ".cache"
}

IGNORE_FILES = {
    ".DS_Store", "Thumbs.db", ".gitignore", ".gitattributes",
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.exe", "*.dll"
}

READABLE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".lua", ".dart", ".ex", ".exs",
    ".hs", ".ml", ".clj", ".vue", ".svelte", ".html", ".css", ".scss", ".sass",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
    ".md", ".txt", ".env.example", ".dockerfile", "dockerfile", ".makefile"
}

# ⚠ Files that often contain secrets — read metadata only, never content
SENSITIVE_FILENAMES = {
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    "secrets.yml", "secrets.yaml", "credentials", "id_rsa", "id_ed25519",
    "id_ecdsa", "id_dsa", ".netrc", ".npmrc", "auth.json",
}

MAX_FILE_SIZE  = 15_000
MAX_TOTAL_SIZE = 80_000
MAX_FILES      = 50

# Allowed URL schemes for --base-url (blocks file://, ftp://, etc.)
ALLOWED_URL_SCHEMES = {"http", "https"}

# Cloud provider URLs must use HTTPS
CLOUD_PROVIDERS = {"groq", "gemini", "deepseek", "kimi", "glm"}

# ─── Provider Registry ────────────────────────────────────────────────────────

PROVIDERS = {
    "groq": {
        "env":    "GROQ_API_KEY",
        "model":  "llama3-70b-8192",
        "url":    "https://api.groq.com/openai/v1/chat/completions",
        "style":  "openai",
        "free":   True,
        "signup": "https://console.groq.com",
        "note":   "Very fast, generous free tier",
    },
    "gemini": {
        "env":    "GEMINI_API_KEY",
        "model":  "gemini-1.5-flash",
        "url":    None,
        "style":  "gemini",
        "free":   True,
        "signup": "https://aistudio.google.com/app/apikey",
        "note":   "Google free tier",
    },
    "deepseek": {
        "env":    "DEEPSEEK_API_KEY",
        "model":  "deepseek-chat",
        "url":    "https://api.deepseek.com/chat/completions",
        "style":  "openai",
        "free":   True,
        "signup": "https://platform.deepseek.com",
        "note":   "Free tier with generous quota",
    },
    "kimi": {
        "env":    "KIMI_API_KEY",
        "model":  "moonshot-v1-8k",
        "url":    "https://api.moonshot.cn/v1/chat/completions",
        "style":  "openai",
        "free":   True,
        "signup": "https://platform.moonshot.cn",
        "note":   "Moonshot AI (Kimi), free trial credits",
    },
    "glm": {
        "env":    "GLM_API_KEY",
        "model":  "glm-4-flash",
        "url":    "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "style":  "openai",
        "free":   True,
        "signup": "https://open.bigmodel.cn",
        "note":   "Zhipu GLM-4-Flash is free",
    },
    "ollama": {
        "env":    None,
        "model":  "llama3",
        "url":    "http://localhost:11434/api/generate",
        "style":  "ollama",
        "free":   True,
        "signup": "https://ollama.com",
        "note":   "100% local, no internet or key needed",
    },
    "lmstudio": {
        "env":    None,
        "model":  None,
        "url":    "http://localhost:1234/v1/chat/completions",
        "style":  "openai",
        "free":   True,
        "signup": "https://lmstudio.ai",
        "note":   "Local models via LM Studio, no key needed",
    },
}

PROVIDER_CHOICES = list(PROVIDERS.keys())

# ─── Security Helpers ─────────────────────────────────────────────────────────

def validate_url(url: str, require_https: bool = False) -> str:
    """
    [SEC-1] SSRF / URL Scheme Validation
    Rejects file://, ftp://, javascript://, and other unexpected schemes.
    Cloud providers always require HTTPS.
    """
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValueError(f"Malformed URL: {url!r}")

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"Disallowed URL scheme {scheme!r} in {url!r}. "
            f"Only {ALLOWED_URL_SCHEMES} are permitted."
        )
    if require_https and scheme != "https":
        raise ValueError(
            f"Cloud provider URL must use HTTPS, got: {url!r}"
        )
    if not parsed.netloc:
        raise ValueError(f"URL has no host: {url!r}")

    return url


def is_safe_output_path(root: Path, output: str) -> Path:
    """
    [SEC-2] Path Traversal Prevention for --output
    Ensures the output file stays inside the repo root, blocking e.g.
    --output ../../etc/crontab or --output /etc/passwd
    """
    # Resolve relative to root, then check it's still inside root
    candidate = (root / output).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise ValueError(
            f"Output path escapes the repository root.\n"
            f"  Requested: {candidate}\n"
            f"  Root:      {root.resolve()}\n"
            f"Use a relative path like 'docs/README.md'."
        )
    return candidate


def is_safe_file(path: Path, root: Path) -> bool:
    """
    [SEC-3] Symlink + Path Traversal Guard for file reading
    Ensures symlinks don't escape the repo and sensitive files are skipped.
    """
    # Resolve symlinks and verify the real path is still inside the root
    try:
        real = path.resolve()
        real.relative_to(root.resolve())
    except (ValueError, OSError):
        return False   # symlink escapes root → skip

    # Skip files that commonly hold secrets
    if path.name.lower() in SENSITIVE_FILENAMES:
        return False

    return True


def redact_key(key: str) -> str:
    """[SEC-4] Never print a full API key — show only first/last 4 chars."""
    if not key or len(key) < 10:
        return "***"
    return f"{key[:4]}…{key[-4:]}"

# ─── Repo Scanner ─────────────────────────────────────────────────────────────

def should_ignore(path: Path) -> bool:
    name = path.name.lower()
    for pattern in IGNORE_FILES:
        if pattern.startswith("*"):
            if name.endswith(pattern[1:]):
                return True
        elif name == pattern.lower():
            return True
    return False


def scan_repo(root: Path) -> dict:
    structure     = []
    files_content = {}
    total_chars   = 0
    files_read    = 0
    skipped_sensitive = 0

    priority_files = [
        "readme.md", "readme.txt", "setup.py", "setup.cfg", "pyproject.toml",
        "package.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
        "makefile", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
        "requirements.txt", "pipfile", "gemfile", "composer.json",
        ".env.example", "main.py", "app.py", "index.js", "index.ts",
        "main.go", "main.rs", "src/main.rs", "src/lib.rs"
    ]

    # Build directory tree
    for path in sorted(root.rglob("*")):
        rel   = path.relative_to(root)
        parts = rel.parts
        if any(p in IGNORE_DIRS or p.endswith(".egg-info") for p in parts):
            continue
        if should_ignore(path):
            continue
        # [SEC-3] Skip symlinks that escape root in tree display too
        if path.is_symlink() and not is_safe_file(path, root):
            continue
        depth  = len(parts) - 1
        indent = "  " * depth
        icon   = "📁 " if path.is_dir() else "📄 "
        structure.append(f"{indent}{icon}{path.name}")

    # Collect readable files
    all_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel   = path.relative_to(root)
        parts = rel.parts
        if any(p in IGNORE_DIRS or p.endswith(".egg-info") for p in parts):
            continue
        if should_ignore(path):
            continue

        # [SEC-3] Symlink + sensitive file guard
        if not is_safe_file(path, root):
            if path.name.lower() in SENSITIVE_FILENAMES:
                skipped_sensitive += 1
            continue

        rel_str     = str(rel).lower().replace("\\", "/")
        is_priority = rel_str in priority_files or path.name.lower() in priority_files
        suffix      = path.suffix.lower()
        is_readable = suffix in READABLE_EXTENSIONS or path.name.lower() in READABLE_EXTENSIONS
        if is_readable:
            all_files.append((is_priority, path, rel))

    all_files.sort(key=lambda x: (not x[0], str(x[2])))

    for _, path, rel in all_files:
        if files_read >= MAX_FILES or total_chars >= MAX_TOTAL_SIZE:
            break
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(content) > MAX_FILE_SIZE:
                content = content[:MAX_FILE_SIZE] + f"\n... [truncated, {len(content)} chars total]"
            files_content[str(rel)] = content
            total_chars += len(content)
            files_read  += 1
        except OSError as exc:
            # [SEC-5] Log specific OS errors (permission denied, broken symlink)
            # but never silently swallow them all — helps detect access issues
            print(f"⚠️  Skipping {path}: {exc}", file=sys.stderr)

    return {
        "structure":          "\n".join(structure[:200]),
        "files":              files_content,
        "total_files_read":   files_read,
        "total_chars":        total_chars,
        "skipped_sensitive":  skipped_sensitive,
    }

# ─── AI Callers ───────────────────────────────────────────────────────────────

def _http_post(url: str, payload: dict, headers: dict, timeout: int = 90) -> dict:
    """
    [SEC-1] URL is validated before reaching here.
    Uses the default SSL context so certificate verification is always on.
    """
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=headers)
    # ssl.create_default_context() enforces cert verification (no ssl.CERT_NONE)
    ctx  = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        raw = resp.read()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response from {url}: {exc}") from exc


def call_openai_compat(prompt: str, url: str, api_key: str, model: str) -> str:
    validate_url(url)   # [SEC-1]
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload: dict = {
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens":  4096,
    }
    if model:
        payload["model"] = model
    data = _http_post(url, payload, headers)
    return data["choices"][0]["message"]["content"]


def call_gemini(prompt: str, api_key: str, model: str) -> str:
    # model name comes from our own PROVIDERS dict — still sanitise it
    safe_model = model.replace("/", "").replace("..", "")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{safe_model}:generateContent"
    )
    # Key goes in query string — urllib handles encoding
    full_url = f"{url}?key={urllib.parse.quote(api_key, safe='')}"
    validate_url(full_url, require_https=True)  # [SEC-1]
    data = _http_post(full_url, {
        "contents":         [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
    }, {"Content-Type": "application/json"})
    return data["candidates"][0]["content"]["parts"][0]["text"]


def call_ollama(prompt: str, model: str, base_url: str = "http://localhost:11434") -> str:
    validate_url(base_url)  # [SEC-1] blocks file:// etc even for local
    url  = f"{base_url.rstrip('/')}/api/generate"
    validate_url(url)
    data = _http_post(url, {
        "model":  model,
        "prompt": prompt,
        "stream": False,
    }, {"Content-Type": "application/json"}, timeout=180)
    return data["response"]


def call_provider(provider: str, prompt: str, model: str, api_key: str, base_url: str = None) -> str:
    cfg   = PROVIDERS[provider]
    style = cfg["style"]

    # [SEC-1] For cloud providers, always enforce HTTPS on their fixed URLs
    if provider in CLOUD_PROVIDERS and cfg.get("url"):
        validate_url(cfg["url"], require_https=True)

    # [SEC-1] Validate user-supplied --base-url
    if base_url:
        require_https = provider in CLOUD_PROVIDERS
        validate_url(base_url, require_https=require_https)

    url = base_url or cfg["url"]

    if style == "gemini":
        return call_gemini(prompt, api_key, model)
    elif style == "ollama":
        ollama_base = base_url or "http://localhost:11434"
        return call_ollama(prompt, model, ollama_base)
    else:
        return call_openai_compat(prompt, url, api_key, model)

# ─── Prompt Builder ───────────────────────────────────────────────────────────

def build_prompt(repo_data: dict, repo_name: str) -> str:
    files_section = ""
    for filepath, content in repo_data["files"].items():
        files_section += f"\n\n### File: `{filepath}`\n```\n{content}\n```"

    return f"""You are an expert technical writer. Analyze this code repository and generate a comprehensive, professional README.md file.

Repository name: {repo_name}

## Repository Structure:
{repo_data['structure']}

## File Contents:
{files_section}

---

Generate a complete README.md with these sections (only include sections that are relevant):

1. **Project Title & Badges** - Name, short tagline, relevant badges (build, license, version)
2. **Description** - What the project does, why it exists, key features (bullet list)
3. **Demo / Screenshot** - Note if applicable (placeholder is fine)
4. **Tech Stack** - Languages, frameworks, key dependencies
5. **Prerequisites** - What's needed before installing
6. **Installation** - Step-by-step setup commands
7. **Usage** - How to run/use it, with code examples
8. **Configuration** - Environment variables, config files explained
9. **Project Structure** - Brief explanation of key folders/files
10. **API Reference** - If it's a library or has an API
11. **Contributing** - How to contribute
12. **License** - Based on any license file found, otherwise suggest MIT

Rules:
- Use real information from the code — never fabricate
- Use proper Markdown formatting with correct heading levels
- All code blocks must have a language tag
- Be concise but thorough
- Unknown values: use a clear placeholder like `[Add description here]`
- Output ONLY the raw Markdown content, no preamble, no explanation, no code fences wrapping the whole output
"""

# ─── GitHub Actions Workflow Generator ────────────────────────────────────────

def generate_workflow(provider: str) -> str:
    cfg   = PROVIDERS[provider]
    style = cfg["style"]

    if style == "ollama" or provider == "lmstudio":
        return (
            "# ⚠️  Local providers (Ollama, LM Studio) cannot run in GitHub Actions.\n"
            "# Use a cloud provider: groq, gemini, deepseek, kimi, or glm.\n"
        )

    env_var   = cfg.get("env") or ""
    env_block = f"\n        env:\n          {env_var}: ${{{{ secrets.{env_var} }}}}" if env_var else ""

    return f"""# .github/workflows/readme.yml
# Automatically regenerates README.md on every push to main.
#
# Setup:
#   1. Go to Settings → Secrets and variables → Actions
#   2. Add a new secret named: {env_var or 'N/A'}
#      Get your key at: {cfg['signup']}
#   3. Commit this file — the workflow runs automatically.

name: Generate README

on:
  push:
    branches: [main, master]
    paths-ignore:
      - 'README.md'       # prevent infinite loop
  workflow_dispatch:       # allow manual runs from the Actions tab

permissions:
  contents: write

jobs:
  generate-readme:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Generate README
        run: python readmegen.py . --provider {provider} --overwrite{env_block}

      - name: Commit updated README
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add README.md
          git diff --staged --quiet || git commit -m "docs: auto-update README [skip ci]"
          git push
"""

# ─── Helpers ──────────────────────────────────────────────────────────────────

def detect_provider():
    order = ["groq", "gemini", "deepseek", "kimi", "glm"]
    for name in order:
        env = PROVIDERS[name].get("env")
        if env and os.getenv(env):
            return name, os.getenv(env)
    # Probe LM Studio — connection refused is fine (expected when not running)
    try:
        urllib.request.urlopen(
            "http://localhost:1234/v1/models",
            timeout=2,
            context=ssl.create_default_context()
        )
        return "lmstudio", ""
    except (urllib.error.URLError, OSError):
        # URLError covers connection refused / timeout — expected
        pass
    except Exception:
        # Any other error: still fall through to Ollama
        pass
    return "ollama", ""


def clean_readme(text: str) -> str:
    text = text.strip()
    for prefix in ("```markdown", "```md", "```"):
        if text.startswith(prefix):
            text = text[len(prefix):].lstrip()
            break
    if text.endswith("```"):
        text = text[:-3].rstrip()
    return text


def print_providers_table():
    print(f"\n  {'Provider':<12} {'Free?':<7} {'Env Variable':<22} Note")
    print(f"  {'-'*12} {'-'*6} {'-'*22} {'-'*38}")
    for name, cfg in PROVIDERS.items():
        env  = cfg.get("env") or "— (no key needed)"
        free = "✅" if cfg["free"] else "💰"
        print(f"  {name:<12} {free:<7} {env:<22} {cfg['note']}")
    print()

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=f"🤖 readmegen v{__version__} — AI-powered README generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  readmegen                               auto-detect provider, current dir
  readmegen ./my-project                  specific repo path
  readmegen --provider groq               Groq  (needs GROQ_API_KEY)
  readmegen --provider deepseek           DeepSeek  (needs DEEPSEEK_API_KEY)
  readmegen --provider kimi               Kimi / Moonshot  (needs KIMI_API_KEY)
  readmegen --provider glm                Zhipu GLM  (needs GLM_API_KEY)
  readmegen --provider gemini             Google Gemini  (needs GEMINI_API_KEY)
  readmegen --provider ollama             local Ollama, no key needed
  readmegen --provider ollama --model mistral
  readmegen --provider lmstudio           local LM Studio, no key needed
  readmegen --provider lmstudio --base-url http://192.168.1.5:1234
  readmegen --output docs/README.md       custom output path
  readmegen --dry-run                     preview prompt only, no AI call
  readmegen --gen-workflow groq           print GitHub Actions YAML
  readmegen --gen-workflow groq --save-workflow   save workflow file
  readmegen --list-providers              show all providers
        """
    )
    parser.add_argument("path",             nargs="?", default=".",
                        help="Repository path (default: current directory)")
    parser.add_argument("--provider",       choices=PROVIDER_CHOICES,
                        help="AI provider (auto-detected if omitted)")
    parser.add_argument("--model",          default=None,
                        help="Model name override (e.g. mistral, llama3, deepseek-coder)")
    parser.add_argument("--base-url",       default=None,
                        help="Override API base URL (useful for remote Ollama / LM Studio)")
    parser.add_argument("--output",         default="README.md",
                        help="Output file (default: README.md)")
    parser.add_argument("--overwrite",      action="store_true",
                        help="Overwrite existing README without prompting")
    parser.add_argument("--dry-run",        action="store_true",
                        help="Print prompt preview without calling AI")
    parser.add_argument("--gen-workflow",   metavar="PROVIDER",
                        help="Print a GitHub Actions workflow for the given provider")
    parser.add_argument("--save-workflow",  action="store_true",
                        help="Save workflow to .github/workflows/readme.yml (use with --gen-workflow)")
    parser.add_argument("--list-providers", action="store_true",
                        help="List all supported providers and exit")
    parser.add_argument("--version",        action="version", version=f"readmegen {__version__}")
    args = parser.parse_args()

    # ── Special commands ──────────────────────────────────────────────────────

    if args.list_providers:
        print_providers_table()
        return
    # Show banner for normal runs (skip for list-providers and gen-workflow)
    if not args.list_providers and not args.gen_workflow:
        print(BANNER)
    
    if args.gen_workflow:
        p = args.gen_workflow
        if p not in PROVIDERS:
            print(f"❌ Unknown provider '{p}'. Choose from: {', '.join(PROVIDER_CHOICES)}")
            sys.exit(1)
        workflow = generate_workflow(p)
        if args.save_workflow:
            root    = Path(args.path).resolve()
            wf_path = root / ".github" / "workflows" / "readme.yml"
            wf_path.parent.mkdir(parents=True, exist_ok=True)
            wf_path.write_text(workflow, encoding="utf-8")
            print(f"✅ Workflow saved to: {wf_path}")
        else:
            print(workflow)
        return

    # ── Repo scan ─────────────────────────────────────────────────────────────

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"❌ '{root}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # [SEC-2] Validate --output path before scanning (fast-fail)
    try:
        output_path = is_safe_output_path(root, args.output)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    # [SEC-1] Validate --base-url early
    if args.base_url:
        provider_for_check = args.provider or "ollama"
        require_https      = provider_for_check in CLOUD_PROVIDERS
        try:
            validate_url(args.base_url, require_https=require_https)
        except ValueError as exc:
            print(f"❌ Invalid --base-url: {exc}", file=sys.stderr)
            sys.exit(1)

    repo_name = root.name
    print(f"🔍 Scanning: {root}")

    repo_data = scan_repo(root)
    print(f"📂 {repo_data['total_files_read']} files read ({repo_data['total_chars']:,} chars)")
    if repo_data["skipped_sensitive"]:
        print(f"🔒 {repo_data['skipped_sensitive']} sensitive file(s) skipped (e.g. .env, secrets)")
    print(f"🌳 {len(repo_data['structure'].splitlines())} directory entries")

    prompt = build_prompt(repo_data, repo_name)

    if args.dry_run:
        print("\n" + "─" * 60)
        print("DRY RUN — Prompt preview (first 3 000 chars):")
        print("─" * 60)
        print(prompt[:3000] + ("…" if len(prompt) > 3000 else ""))
        print(f"\nTotal prompt: {len(prompt):,} chars")
        return

    # ── Provider resolution ───────────────────────────────────────────────────

    if args.provider:
        provider = args.provider
        env_var  = PROVIDERS[provider].get("env")
        api_key  = os.getenv(env_var, "") if env_var else ""
    else:
        provider, api_key = detect_provider()
        print(f"🤖 Auto-detected provider: {provider}")

    cfg     = PROVIDERS[provider]
    env_var = cfg.get("env")
    if env_var and not api_key:
        api_key = os.getenv(env_var, "")

    needs_key = provider in CLOUD_PROVIDERS and bool(env_var)
    if needs_key and not api_key:
        print(f"\n❌ No API key for '{provider}'.")
        print(f"   export {env_var}=your_key_here")
        print(f"   Free key at: {cfg['signup']}")
        sys.exit(1)

    model    = args.model or cfg.get("model")
    base_url = args.base_url

    # ── Call AI ───────────────────────────────────────────────────────────────

    label = model or "(server default)"
    # [SEC-4] Never log the actual API key
    if api_key:
        print(f"🔑 Using API key: {redact_key(api_key)}")
    print(f"✨ Generating with {provider} [{label}]…")

    try:
        readme = call_provider(provider, prompt, model, api_key, base_url)
    except ValueError as exc:
        # URL validation or JSON parse errors
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"❌ HTTP {exc.code}: {body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as exc:
        print(f"❌ Connection error: {exc.reason}", file=sys.stderr)
        if provider == "ollama":
            print(f"   Start Ollama:   ollama serve", file=sys.stderr)
            print(f"   Pull the model: ollama pull {model}", file=sys.stderr)
        elif provider == "lmstudio":
            print("   Open LM Studio → load a model → start the local server.", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    readme = clean_readme(readme)

    # ── Write output ──────────────────────────────────────────────────────────

    # output_path already validated above via is_safe_output_path()
    if output_path.exists() and not args.overwrite:
        ans = input(f"⚠️  '{output_path}' exists. Overwrite? [y/N] ").strip().lower()
        if ans != "y":
            print("Aborted.")
            sys.exit(0)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(readme, encoding="utf-8")
    print(f"\n✅ README written to: {output_path}")
    print(f"   {len(readme):,} chars · {len(readme.splitlines())} lines")
    print(f"\n💡 Set up auto-generation on push:")
    print(f"   python readmegen.py --gen-workflow {provider} --save-workflow")


if __name__ == "__main__":
    main()
