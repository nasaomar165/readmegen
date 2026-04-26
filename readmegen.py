#!/usr/bin/env python3
"""
readmegen v0.3.1 — AI-powered README generator for any code repository.

Supported providers:
  Cloud (free tiers): Groq, Google Gemini, DeepSeek, Kimi (Moonshot), GLM (Zhipu)
  Local:              Ollama, LM Studio

Zero pip dependencies — pure Python 3.8+ stdlib.

Configuration priority (lowest → highest):
  1. Hardcoded fallbacks in this script
  2. readmegen_defaults.json  (next to this script — edit once, applies everywhere)
  3. ~/.config/readmegen/config.json  (user-level overrides)
  4. readmegen.json  (per-project, in repo root)
  5. CLI flags  (always win)
"""

from __future__ import annotations

import abc
import difflib
import email.utils
import fnmatch
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ══════════════════════════════════════════════════════════════════════════════
# Version & constants
# ══════════════════════════════════════════════════════════════════════════════

__version__ = "0.3.1"

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

# ── Scan limits (hardcoded fallbacks — overridden by config files) ─────────────

DEFAULT_MAX_FILES       = 50
DEFAULT_MAX_TOTAL_CHARS = 80_000
DEFAULT_MAX_FILE_SIZE   = 15_000

# ── Ignore rules ──────────────────────────────────────────────────────────────

IGNORE_DIR_PATTERNS: List[str] = [
    ".git", ".svn", "node_modules", "__pycache__",
    ".venv", "venv", "env", ".env",
    "dist", "build", ".next", ".nuxt",
    "coverage", ".pytest_cache", ".mypy_cache", ".tox",
    "eggs", ".eggs", "*.egg-info",
    ".idea", ".vscode",
    "target", "out", "bin", "obj", ".gradle", ".cache",
]

IGNORE_FILE_PATTERNS: List[str] = [
    ".ds_store", "thumbs.db", ".gitignore", ".gitattributes",
    "package-lock.json", "yarn.lock", "poetry.lock", "pipfile.lock",
    "*.pyc", "*.pyo", "*.class", "*.o", "*.so", "*.exe", "*.dll",
]

READABLE_EXTENSIONS: frozenset = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".r",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".lua", ".dart", ".ex", ".exs",
    ".hs", ".ml", ".clj", ".vue", ".svelte", ".html", ".css", ".scss", ".sass",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".xml",
    ".md", ".txt", ".env.example",
})

READABLE_NAMES: frozenset = frozenset({
    "dockerfile", ".dockerfile", "makefile", "gemfile", "pipfile",
    "procfile", "vagrantfile",
})

PRIORITY_FILES: List[str] = [
    "readme.md", "readme.txt", "setup.py", "setup.cfg", "pyproject.toml",
    "package.json", "cargo.toml", "go.mod", "pom.xml", "build.gradle",
    "makefile", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "requirements.txt", "pipfile", "gemfile", "composer.json",
    ".env.example", "main.py", "app.py", "index.js", "index.ts",
    "main.go", "main.rs", "src/main.rs", "src/lib.rs",
    ".cursorrules", "claude.md", ".github/copilot-instructions.md",
    "copilot-instructions.md", ".windsurfrules", ".gemini/rules",
]

# ── Sensitive file detection ───────────────────────────────────────────────────

SENSITIVE_EXACT: frozenset = frozenset({
    ".env", ".env.local", ".env.production", ".env.staging", ".env.development",
    "secrets.yml", "secrets.yaml", "credentials", "auth.json",
    "id_rsa", "id_ed25519", "id_ecdsa", "id_dsa",
    ".netrc", ".npmrc",
})

SENSITIVE_GLOB_PATTERNS: List[str] = [
    "*.pem", "*.key", "*.crt", "*.p12", "*.pfx",
    "secrets.*", "secret.*",
    "credentials.*", "credential.*",
    "password.*", "passwords.*",
    ".env.*",
]

# ── Security ───────────────────────────────────────────────────────────────────

ALLOWED_URL_SCHEMES: frozenset = frozenset({"http", "https"})
CLOUD_PROVIDERS: frozenset     = frozenset({"groq", "gemini", "deepseek", "kimi", "glm"})

# ── Retry policy ──────────────────────────────────────────────────────────────

RETRY_MAX      = 3
RETRY_STATUSES = {429, 500, 502, 503, 504}

# ── Secret-masking regex ──────────────────────────────────────────────────────

_SECRET_PATTERN = re.compile(
    r'(?i)(?<![A-Z0-9_])([A-Z0-9_]*(?:KEY|SECRET|PASSWORD|TOKEN|CREDENTIAL)[A-Z0-9_]*\s*=\s*)\S+',
    re.MULTILINE,
)

# ── Extension → language name ─────────────────────────────────────────────────

EXT_LANG_MAP: Dict[str, str] = {
    ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript", ".tsx": "TypeScript (TSX)",
    ".go": "Go", ".rs": "Rust", ".java": "Java",
    ".c": "C", ".cpp": "C++", ".h": "C/C++ Header", ".hpp": "C++ Header",
    ".cs": "C#", ".rb": "Ruby", ".php": "PHP", ".swift": "Swift",
    ".kt": "Kotlin", ".scala": "Scala", ".r": "R",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".fish": "Shell",
    ".ps1": "PowerShell", ".lua": "Lua", ".dart": "Dart",
    ".ex": "Elixir", ".exs": "Elixir", ".hs": "Haskell", ".ml": "OCaml",
    ".clj": "Clojure", ".vue": "Vue", ".svelte": "Svelte",
    ".html": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "SASS",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".ini": "INI", ".cfg": "Config", ".conf": "Config", ".xml": "XML",
    ".md": "Markdown", ".txt": "Text",
}

# ── License detection ─────────────────────────────────────────────────────────

_LICENSE_PATTERN = re.compile(
    r'(MIT License|Apache License.*?Version 2\.0|GNU GENERAL PUBLIC LICENSE.*?v?3|'
    r'BSD [23]-Clause|ISC License|Mozilla Public License.*?2\.0|'
    r'The Unlicense|\b0BSD\b)',
    re.IGNORECASE | re.DOTALL,
)

_LICENSE_SHORT_MAP: Dict[str, str] = {
    "mit license": "MIT",
    "apache license": "Apache-2.0",
    "gnu general public license": "GPL-3.0",
    "bsd 2-clause": "BSD-2-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "isc license": "ISC",
    "mozilla public license": "MPL-2.0",
    "the unlicense": "Unlicense",
    "0bsd": "0BSD",
}

_LICENSE_FILE_NAMES = frozenset({
    "license", "licence", "license.md", "licence.md",
    "license.txt", "licence.txt",
})

# ── Config file arg mapping ───────────────────────────────────────────────────

_CONFIG_ARG_MAP: Dict[str, str] = {
    "provider": "provider",
    "model": "model",
    "base_url": "base_url",
    "output": "output",
    "language": "language",
    "max_files": "max_files",
    "max_total_chars": "max_total_chars",
    "max_file_size": "max_file_size",
    "timeout": "timeout",
    "overwrite": "overwrite",
    "backup": "backup",
    "git_context": "git_context",
}

# ══════════════════════════════════════════════════════════════════════════════
# Provider registry
# ══════════════════════════════════════════════════════════════════════════════

PROVIDERS: Dict[str, dict] = {
    "groq": {
        "env":              "GROQ_API_KEY",
        "model":            "llama3-70b-8192",
        "url":              "https://api.groq.com/openai/v1/chat/completions",
        "style":            "openai",
        "free":             True,
        "signup":           "https://console.groq.com",
        "note":             "Very fast, generous free tier",
        "max_prompt_tokens": 28000,
    },
    "gemini": {
        "env":              "GEMINI_API_KEY",
        "model":            "gemini-1.5-flash",
        "url":              None,
        "style":            "gemini",
        "free":             True,
        "signup":           "https://aistudio.google.com/app/apikey",
        "note":             "Google free tier",
        "max_prompt_tokens": 900000,
    },
    "deepseek": {
        "env":              "DEEPSEEK_API_KEY",
        "model":            "deepseek-chat",
        "url":              "https://api.deepseek.com/chat/completions",
        "style":            "openai",
        "free":             True,
        "signup":           "https://platform.deepseek.com",
        "note":             "Free tier with generous quota",
        "max_prompt_tokens": 56000,
    },
    "kimi": {
        "env":              "KIMI_API_KEY",
        "model":            "moonshot-v1-8k",
        "url":              "https://api.moonshot.cn/v1/chat/completions",
        "style":            "openai",
        "free":             True,
        "signup":           "https://platform.moonshot.cn",
        "note":             "Moonshot AI (Kimi), free trial credits",
        "max_prompt_tokens": 7000,
    },
    "glm": {
        "env":              "GLM_API_KEY",
        "model":            "glm-4-flash",
        "url":              "https://open.bigmodel.cn/api/paas/v4/chat/completions",
        "style":            "openai",
        "free":             True,
        "signup":           "https://open.bigmodel.cn",
        "note":             "Zhipu GLM-4-Flash is free",
        "max_prompt_tokens": 110000,
    },
    "ollama": {
        "env":              None,
        "model":            "llama3",
        "url":              "http://localhost:11434/api/generate",
        "style":            "ollama",
        "free":             True,
        "signup":           "https://ollama.com",
        "note":             "100% local, no internet or key needed",
        "max_prompt_tokens": 28000,
    },
    "lmstudio": {
        "env":              None,
        "model":            None,
        "url":              "http://localhost:1234/v1/chat/completions",
        "style":            "openai",
        "free":             True,
        "signup":           "https://lmstudio.ai",
        "note":             "Local models via LM Studio, no key needed",
        "max_prompt_tokens": 28000,
    },
}

PROVIDER_CHOICES: List[str] = list(PROVIDERS.keys())

# ══════════════════════════════════════════════════════════════════════════════
# Config file loader  (4-tier priority system)
# ══════════════════════════════════════════════════════════════════════════════

def _script_dir() -> Path:
    """Return the directory containing readmegen.py."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        # __file__ not defined (rare — e.g. pydoc)
        return Path.cwd()


def _load_json_file(path: Path) -> Dict[str, Any]:
    """Read and parse a JSON file. Returns empty dict on any error."""
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return data
        return {}
    except (json.JSONDecodeError, OSError):
        return {}


def _xdg_config_home() -> Path:
    """Return ~/.config/readmegen, respecting XDG_CONFIG_HOME."""
    xdg = os.getenv("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "readmegen"


def load_all_configs(verbose: bool = False) -> Dict[str, Any]:
    """
    Load and merge configuration from all tiers (lowest → highest priority):

      1. readmegen_defaults.json   (next to this script — ships with the tool)
      2. ~/.config/readmegen/config.json  (user-level — personal overrides)
      3. (readmegen.json in repo root is loaded later in main() after we know the repo)

    Returns the merged dict.  Later tiers overwrite earlier keys.
    Keys starting with ``_`` are treated as comments and stripped.
    """
    merged: Dict[str, Any] = {}

    # Tier 1: Shipped defaults (next to script)
    shipped = _script_dir() / "readmegen_defaults.json"
    tier1 = _load_json_file(shipped)
    if tier1 and verbose:
        print(f"⚙️  Loaded shipped defaults: {shipped}")
    merged.update(tier1)

    # Tier 2: User-level config
    user_dir = _xdg_config_home()
    user_cfg = user_dir / "config.json"
    tier2 = _load_json_file(user_cfg)
    if tier2 and verbose:
        print(f"⚙️  Loaded user config: {user_cfg}")
    merged.update(tier2)

    # Strip comment keys (start with _)
    merged = {k: v for k, v in merged.items() if not k.startswith("_")}

    return merged


def load_project_config(root: Path, verbose: bool = False) -> Dict[str, Any]:
    """Tier 3: Load readmegen.json from the repository root."""
    project_cfg = root / "readmegen.json"
    data = _load_json_file(project_cfg)
    if data and verbose:
        print(f"⚙️  Loaded project config: {project_cfg}")
    return data

# ══════════════════════════════════════════════════════════════════════════════
# Security helpers
# ══════════════════════════════════════════════════════════════════════════════

def validate_url(url: str, require_https: bool = False) -> str:
    if not url:
        raise ValueError("URL must not be empty.")
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as exc:
        raise ValueError(f"Malformed URL {url!r}: {exc}") from exc

    scheme = parsed.scheme.lower()
    if scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(
            f"Disallowed URL scheme {scheme!r} in {url!r}. "
            f"Only {sorted(ALLOWED_URL_SCHEMES)} are permitted."
        )
    if require_https and scheme != "https":
        raise ValueError(f"Cloud provider URL must use HTTPS, got: {url!r}")
    if not parsed.netloc:
        raise ValueError(f"URL has no host: {url!r}")
    return url


def is_safe_output_path(root: Path, output: str) -> Path:
    candidate = (root / output).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        raise ValueError(
            f"Output path escapes the repository root.\n"
            f"  Requested : {candidate}\n"
            f"  Root      : {root.resolve()}\n"
            f"Use a relative path such as 'docs/README.md'."
        )
    return candidate


def _is_sensitive_file(name: str) -> bool:
    lower = name.lower()
    if lower in SENSITIVE_EXACT:
        return True
    return any(fnmatch.fnmatch(lower, pat) for pat in SENSITIVE_GLOB_PATTERNS)


def is_safe_file(path: Path, root: Path) -> bool:
    try:
        real = path.resolve()
        real.relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    if _is_sensitive_file(path.name):
        return False
    return True


def redact_key(key: str) -> str:
    if not key or len(key) < 10:
        return "***"
    return f"{key[:4]}…{key[-4:]}"


def mask_secrets_in_text(text: str) -> str:
    return _SECRET_PATTERN.sub(lambda m: m.group(1) + "[REDACTED]", text)

# ══════════════════════════════════════════════════════════════════════════════
# Ignore-rule helpers
# ══════════════════════════════════════════════════════════════════════════════

def _matches_ignore(name: str, patterns: List[str]) -> bool:
    lower = name.lower()
    return any(fnmatch.fnmatch(lower, pat.lower()) for pat in patterns)


def _dir_part_ignored(part: str) -> bool:
    return _matches_ignore(part, IGNORE_DIR_PATTERNS)


def _file_ignored(name: str) -> bool:
    return _matches_ignore(name, IGNORE_FILE_PATTERNS)


def load_readmegenignore(root: Path) -> Tuple[List[str], List[str], int]:
    ignore_path = root / ".readmegenignore"
    if not ignore_path.is_file():
        return [], [], 0
    try:
        lines = ignore_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], [], 0

    extra_dirs: List[str] = []
    extra_files: List[str] = []
    count = 0
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("/"):
            extra_dirs.append(line.rstrip("/"))
        else:
            extra_files.append(line)
        count += 1

    IGNORE_DIR_PATTERNS.extend(extra_dirs)
    IGNORE_FILE_PATTERNS.extend(extra_files)
    return extra_dirs, extra_files, count

# ══════════════════════════════════════════════════════════════════════════════
# License detection
# ══════════════════════════════════════════════════════════════════════════════

def detect_license(root: Path) -> Optional[str]:
    for candidate in root.iterdir():
        if not candidate.is_file():
            continue
        if candidate.name.lower().replace(".", "") not in _LICENSE_FILE_NAMES and not re.match(
            r'^licen[sc]e\.', candidate.name.lower()
        ):
            continue
        try:
            head = candidate.read_text(encoding="utf-8", errors="ignore")[:500]
        except OSError:
            continue
        m = _LICENSE_PATTERN.search(head)
        if m:
            matched_text = m.group(0).strip()
            for key, short in _LICENSE_SHORT_MAP.items():
                if key in matched_text.lower():
                    return short
            return matched_text.split("\n")[0].strip()[:60]
    return None

# ══════════════════════════════════════════════════════════════════════════════
# Git context helper
# ══════════════════════════════════════════════════════════════════════════════

def get_git_log(root: Path, count: int = 20) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "log", "--oneline", f"-{count}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return None

# ══════════════════════════════════════════════════════════════════════════════
# Diff helper
# ══════════════════════════════════════════════════════════════════════════════

def show_diff(old_text: str, new_text: str, max_lines: int = 80) -> str:
    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile="current", tofile="generated", n=3,
    ))
    if not diff_lines:
        return ""
    if len(diff_lines) > max_lines:
        truncated = len(diff_lines) - max_lines
        diff_lines = diff_lines[:max_lines]
        diff_lines.append(f"\n... ({truncated} more lines)\n")
    return "".join(diff_lines)

# ══════════════════════════════════════════════════════════════════════════════
# Repo scanner
# ══════════════════════════════════════════════════════════════════════════════

def scan_repo(
    root: Path,
    max_files: int       = DEFAULT_MAX_FILES,
    max_total: int       = DEFAULT_MAX_TOTAL_CHARS,
    max_file_size: int   = DEFAULT_MAX_FILE_SIZE,
    verbose: bool        = False,
) -> dict:
    structure:         List[str]       = []
    files_content:     Dict[str, str]  = {}
    total_chars:       int             = 0
    files_read:        int             = 0
    skipped_sensitive: int             = 0
    lang_counts:       Dict[str, int]  = {}

    def _should_skip_parts(parts: Tuple[str, ...]) -> bool:
        return any(_dir_part_ignored(p) for p in parts)

    # ── Directory tree ────────────────────────────────────────────────────────
    for path in sorted(root.rglob("*")):
        try:
            rel   = path.relative_to(root)
            parts = rel.parts
        except ValueError:
            continue
        if _should_skip_parts(parts):
            continue
        if _file_ignored(path.name):
            continue
        if path.is_symlink() and not is_safe_file(path, root):
            continue
        depth  = len(parts) - 1
        indent = "  " * depth
        icon   = "📁 " if path.is_dir() else "📄 "
        structure.append(f"{indent}{icon}{path.name}")

    # ── File collection ───────────────────────────────────────────────────────
    all_files: List[Tuple[bool, Path, Path]] = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel   = path.relative_to(root)
            parts = rel.parts
        except ValueError:
            if verbose:
                print(f"⚠️  Skip {path}: outside root", file=sys.stderr)
            continue
        if _should_skip_parts(parts):
            if verbose:
                skipped_part = next((p for p in parts if _dir_part_ignored(p)), parts[-1])
                print(f"⚠️  Skip {rel}: ignored directory ({skipped_part})", file=sys.stderr)
            continue
        if _file_ignored(path.name):
            if verbose:
                print(f"⚠️  Skip {rel}: ignored file pattern", file=sys.stderr)
            continue

        if not is_safe_file(path, root):
            if _is_sensitive_file(path.name):
                skipped_sensitive += 1
                if verbose:
                    print(f"⚠️  Skip {rel}: sensitive file", file=sys.stderr)
            else:
                if verbose:
                    print(f"⚠️  Skip {rel}: symlink escapes root", file=sys.stderr)
            continue

        rel_str     = str(rel).lower().replace("\\", "/")
        is_priority = (
            rel_str in PRIORITY_FILES
            or path.name.lower() in PRIORITY_FILES
        )
        suffix      = path.suffix.lower()
        is_readable = (
            suffix in READABLE_EXTENSIONS
            or path.name.lower() in READABLE_NAMES
        )
        if not is_readable:
            if verbose:
                print(f"⚠️  Skip {rel}: unreadable extension ({suffix or 'none'})", file=sys.stderr)
            continue

        all_files.append((is_priority, path, rel))

    all_files.sort(key=lambda x: (not x[0], str(x[2])))

    for _, path, rel in all_files:
        if files_read >= max_files or total_chars >= max_total:
            if verbose:
                reason = "max files" if files_read >= max_files else "char limit"
                print(f"⚠️  Scan stopped: {reason} reached", file=sys.stderr)
            break
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            if len(content) > max_file_size:
                cut_point = content.rfind("\n", 0, max_file_size)
                if cut_point > max_file_size // 2:
                    content = content[:cut_point]
                else:
                    content = content[:max_file_size]
                content += f"\n... [truncated — {len(content):,} chars total]"
            files_content[str(rel)] = content
            total_chars += len(content)
            files_read  += 1

            suffix = path.suffix.lower()
            lang = EXT_LANG_MAP.get(suffix)
            if lang:
                lang_counts[lang] = lang_counts.get(lang, 0) + 1

            if verbose and (files_read % 5 == 0 or files_read == max_files):
                print(
                    f"\r   📄 Reading... {files_read}/{max_files} files "
                    f"({total_chars:,} chars)",
                    file=sys.stderr, end="", flush=True,
                )
        except OSError as exc:
            print(f"⚠️  Skipping {path}: {exc}", file=sys.stderr)

    if verbose and files_read > 0:
        print(
            f"\r   📄 Reading... {files_read}/{max_files} files "
            f"({total_chars:,} chars) ✓"
            + " " * 20,
            file=sys.stderr,
        )

    return {
        "structure":         "\n".join(structure[:300]),
        "files":             files_content,
        "total_files_read":  files_read,
        "total_chars":       total_chars,
        "skipped_sensitive": skipped_sensitive,
        "lang_counts":       lang_counts,
    }

# ══════════════════════════════════════════════════════════════════════════════
# Provider abstraction
# ══════════════════════════════════════════════════════════════════════════════

class BaseProvider(abc.ABC):
    DEFAULT_TIMEOUT = 90

    def __init__(
        self,
        cfg: dict,
        api_key: str,
        model: Optional[str],
        base_url: Optional[str],
        timeout: Optional[int] = None,
    ) -> None:
        self.cfg      = cfg
        self.api_key  = api_key
        self.model    = model or cfg.get("model") or "default"
        self.base_url = base_url
        self.timeout  = timeout if timeout is not None else self.DEFAULT_TIMEOUT

    @abc.abstractmethod
    def call(self, prompt: str) -> str:
        ...

    @staticmethod
    def _http_post(url: str, payload: dict, headers: dict, timeout: int = 90) -> dict:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req  = urllib.request.Request(url, data=data, headers=headers)
        ctx  = ssl.create_default_context()
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read()
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from {url}: {exc}") from exc


class OpenAICompatProvider(BaseProvider):
    def call(self, prompt: str) -> str:
        url = self.base_url or self.cfg["url"]
        validate_url(url)
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload: dict = {
            "messages":    [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "max_tokens":  4096,
        }
        if self.model:
            payload["model"] = self.model
        data = self._http_post(url, payload, headers, timeout=self.timeout)
        return data["choices"][0]["message"]["content"]


class GeminiProvider(BaseProvider):
    def call(self, prompt: str) -> str:
        safe_model = re.sub(r"[^a-zA-Z0-9._-]", "", self.model)
        base = "https://generativelanguage.googleapis.com/v1beta/models"
        url  = f"{base}/{safe_model}:generateContent"
        full = f"{url}?key={urllib.parse.quote(self.api_key, safe='')}"
        validate_url(full, require_https=True)
        data = self._http_post(full, {
            "contents":         [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 4096},
        }, {"Content-Type": "application/json"}, timeout=self.timeout)
        return data["candidates"][0]["content"]["parts"][0]["text"]


class OllamaProvider(BaseProvider):
    DEFAULT_TIMEOUT = 180

    def call(self, prompt: str) -> str:
        ollama_base = self.base_url or "http://localhost:11434"
        validate_url(ollama_base)
        url = f"{ollama_base.rstrip('/')}/api/generate"
        validate_url(url)
        effective_timeout = max(self.timeout, 180)
        data = self._http_post(url, {
            "model":  self.model,
            "prompt": prompt,
            "stream": False,
        }, {"Content-Type": "application/json"}, timeout=effective_timeout)
        return data["response"]


_STYLE_MAP: Dict[str, type] = {
    "openai": OpenAICompatProvider,
    "gemini": GeminiProvider,
    "ollama": OllamaProvider,
}


def build_provider(
    provider_name: str,
    api_key: str,
    model: Optional[str],
    base_url: Optional[str],
    timeout: Optional[int] = None,
) -> BaseProvider:
    cfg   = PROVIDERS[provider_name]
    style = cfg["style"]
    cls   = _STYLE_MAP.get(style)
    if cls is None:
        raise ValueError(f"Unknown provider style {style!r} for {provider_name!r}")

    if provider_name in CLOUD_PROVIDERS and cfg.get("url"):
        validate_url(cfg["url"], require_https=True)
    if base_url:
        validate_url(base_url, require_https=(provider_name in CLOUD_PROVIDERS))

    return cls(cfg, api_key, model, base_url, timeout)

# ══════════════════════════════════════════════════════════════════════════════
# Retry wrapper
# ══════════════════════════════════════════════════════════════════════════════

def _parse_retry_after(header_value: str, fallback: int) -> int:
    try:
        return min(int(header_value), 60)
    except ValueError:
        pass
    try:
        dt = email.utils.parsedate_to_datetime(header_value)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta > 0:
            return min(int(delta), 60)
    except Exception:
        pass
    return fallback


def call_with_retry(
    provider: BaseProvider,
    prompt: str,
    max_retries: int = RETRY_MAX,
    verbose: bool    = False,
) -> str:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return provider.call(prompt)
        except urllib.error.HTTPError as exc:
            if exc.code in RETRY_STATUSES and attempt < max_retries:
                if exc.code == 429:
                    ra = exc.headers.get("Retry-After")
                    if ra:
                        wait = _parse_retry_after(ra, 2 ** attempt)
                    else:
                        wait = 2 ** attempt
                else:
                    wait = 2 ** attempt
                if verbose:
                    print(f"⚠️  HTTP {exc.code} — retrying in {wait}s "
                          f"(attempt {attempt+1}/{max_retries})…", file=sys.stderr)
                time.sleep(wait)
                last_exc = exc
                continue
            raise
        except urllib.error.URLError as exc:
            if attempt < max_retries:
                wait = 2 ** attempt
                if verbose:
                    print(f"⚠️  Network error — retrying in {wait}s "
                          f"(attempt {attempt+1}/{max_retries})…", file=sys.stderr)
                time.sleep(wait)
                last_exc = exc
                continue
            raise
    raise last_exc  # type: ignore[misc]

# ══════════════════════════════════════════════════════════════════════════════
# Prompt builder
# ══════════════════════════════════════════════════════════════════════════════

def build_prompt(
    repo_data: dict,
    repo_name: str,
    language: Optional[str]    = None,
    template: Optional[str]    = None,
    custom_sections: Optional[List[str]] = None,
    git_log: Optional[str]     = None,
    license_id: Optional[str]  = None,
) -> str:
    files_section = ""
    for filepath, content in repo_data["files"].items():
        files_section += f"\n\n### File: `{filepath}`\n```\n{content}\n```"

    git_section = ""
    if git_log:
        git_section = f"\n\n## Recent Git Activity (last 20 commits):\n{git_log}\n"

    license_hint = ""
    if license_id:
        license_hint = f"\n\nThe project uses the {license_id} license (detected from LICENSE file).\n"

    if template is not None:
        has_placeholder = any(
            ph in template
            for ph in ("{{FILES_SECTION}}", "{{STRUCTURE}}", "{{REPO_NAME}}")
        )
        if has_placeholder:
            body = template
            body = body.replace("{{REPO_NAME}}", repo_name)
            body = body.replace("{{STRUCTURE}}", repo_data["structure"])
            body = body.replace("{{FILES_SECTION}}", files_section)
        else:
            body = template + files_section + git_section + license_hint
    else:
        custom_section_text = ""
        if custom_sections:
            for i, section in enumerate(custom_sections, start=13):
                custom_section_text += (
                    f'{i}. **{section}** — add relevant content based on the code\n'
                )

        body = (
            f"Repository name: {repo_name}\n\n"
            f"## Repository Structure:\n{repo_data['structure']}\n\n"
            f"## File Contents:{files_section}\n"
            f"{git_section}{license_hint}\n"
            "---\n\n"
            "Generate a complete README.md with these sections "
            "(omit any section not relevant to this project):\n\n"
            "1. **Project Title & Badges** — name, tagline, shields (build, license, version)\n"
            "2. **Description** — what it does, why it exists, key features as a bullet list\n"
            "3. **Demo / Screenshot** — placeholder if not applicable\n"
            "4. **Tech Stack** — languages, frameworks, key dependencies\n"
            "5. **Prerequisites** — what must be installed first\n"
            "6. **Installation** — step-by-step commands\n"
            "7. **Usage** — how to run it, with code examples\n"
            "8. **Configuration** — env vars, config files explained\n"
            "9. **Project Structure** — key folders and files\n"
            "10. **API Reference** — if it's a library or exposes an API\n"
            "11. **Contributing** — how to contribute\n"
            "12. **License** — from any LICENSE file found, else suggest MIT\n"
            f"{custom_section_text}\n"
            "Rules:\n"
            "- Use real information from the code — never invent details\n"
            "- Proper Markdown headings and formatting throughout\n"
            "- Every code block must have a language tag\n"
            "- For unknown values use `[Add description here]`\n"
            "- Output ONLY the raw Markdown — no preamble, explanation, or wrapping fences\n"
        )

    lang_instruction = ""
    if language:
        lang_instruction = f"Write the entire README in {language}.\n"

    return (
        "You are an expert technical writer. "
        "Analyze this code repository and generate a comprehensive, professional README.md.\n\n"
        f"{lang_instruction}{body}"
    )

# ══════════════════════════════════════════════════════════════════════════════
# Token-aware prompt trimming
# ══════════════════════════════════════════════════════════════════════════════

def trim_prompt_to_limit(
    prompt: str,
    repo_data: dict,
    repo_name: str,
    provider_name: str,
    language: Optional[str]    = None,
    template: Optional[str]    = None,
    custom_sections: Optional[List[str]] = None,
    git_log: Optional[str]     = None,
    license_id: Optional[str]  = None,
    verbose: bool              = False,
) -> Tuple[str, int]:
    limit = PROVIDERS[provider_name].get("max_prompt_tokens", 28000)
    tokens = estimate_tokens(prompt)
    if tokens <= limit:
        return prompt, 0

    files = dict(repo_data["files"])
    removed = 0

    while estimate_tokens(prompt) > limit and files:
        last_key = list(files.keys())[-1]
        del files[last_key]
        removed += 1
        modified_data = {**repo_data, "files": files}
        prompt = build_prompt(
            modified_data, repo_name, language, template,
            custom_sections, git_log, license_id,
        )

    if verbose and removed:
        print(
            f"⚠️  Trimmed {removed} file(s) to fit token limit "
            f"(~{estimate_tokens(prompt):,} tokens)",
            file=sys.stderr,
        )
    return prompt, removed

# ══════════════════════════════════════════════════════════════════════════════
# GitHub Actions workflow generator
# ══════════════════════════════════════════════════════════════════════════════

def generate_workflow(provider_name: str) -> str:
    cfg   = PROVIDERS[provider_name]
    style = cfg["style"]

    if style == "ollama" or provider_name == "lmstudio":
        return (
            "# ⚠️  Local providers (Ollama, LM Studio) cannot run in GitHub Actions.\n"
            "# Use a cloud provider: groq, gemini, deepseek, kimi, or glm.\n"
        )

    env_var   = cfg.get("env") or ""
    env_block = (
        f"\n        env:\n          {env_var}: ${{{{ secrets.{env_var} }}}}"
        if env_var else ""
    )

    return (
        f"# .github/workflows/readme.yml\n"
        f"# Auto-regenerates README.md on every push to main.\n"
        f"#\n"
        f"# Setup:\n"
        f"#   1. Settings → Secrets and variables → Actions\n"
        f"#   2. Add secret: {env_var or 'N/A'}\n"
        f"#      Free key: {cfg['signup']}\n"
        f"#   3. Commit this file — runs automatically.\n"
        f"\n"
        f"name: Generate README\n"
        f"\n"
        f"on:\n"
        f"  push:\n"
        f"    branches: [main, master]\n"
        f"    paths-ignore:\n"
        f"      - 'README.md'       # prevent infinite loop\n"
        f"  workflow_dispatch:       # allow manual runs\n"
        f"\n"
        f"permissions:\n"
        f"  contents: write\n"
        f"\n"
        f"jobs:\n"
        f"  generate-readme:\n"
        f"    runs-on: ubuntu-latest\n"
        f"\n"
        f"    steps:\n"
        f"      - name: Checkout repository\n"
        f"        uses: actions/checkout@v4\n"
        f"\n"
        f"      - name: Set up Python\n"
        f"        uses: actions/setup-python@v5\n"
        f"        with:\n"
        f"          python-version: '3.11'\n"
        f"\n"
        f"      - name: Generate README\n"
        f"        run: python readmegen.py . --provider {provider_name} --overwrite{env_block}\n"
        f"\n"
        f"      - name: Commit updated README\n"
        f"        run: |\n"
        f"          git config user.name  \"github-actions[bot]\"\n"
        f"          git config user.email \"github-actions[bot]@users.noreply.github.com\"\n"
        f"          git add README.md\n"
        f"          git diff --staged --quiet || git commit -m \"docs: auto-update README [skip ci]\"\n"
        f"          git push\n"
    )

# ══════════════════════════════════════════════════════════════════════════════
# Misc helpers
# ══════════════════════════════════════════════════════════════════════════════

def detect_provider() -> Tuple[str, str]:
    for name in ["groq", "gemini", "deepseek", "kimi", "glm"]:
        env = PROVIDERS[name].get("env")
        if env and os.getenv(env):
            return name, os.getenv(env)  # type: ignore[return-value]
    try:
        urllib.request.urlopen(
            "http://localhost:1234/v1/models",
            timeout=2,
            context=ssl.create_default_context(),
        )
        return "lmstudio", ""
    except (urllib.error.URLError, OSError):
        pass
    except Exception:
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


def estimate_tokens(text: str) -> int:
    return len(text) // 4


def validate_readme(text: str) -> None:
    if len(text) < 200:
        print(
            f"⚠️  Response seems unusually short ({len(text)} chars). "
            f"The AI may have failed.",
            file=sys.stderr,
        )
    if not re.search(r'^#\s', text, re.MULTILINE):
        print(
            "⚠️  No Markdown headings found in output. Result may be malformed.",
            file=sys.stderr,
        )


def print_providers_table() -> None:
    print(f"\n  {'Provider':<12} {'Free?':<7} {'Env Variable':<24} Note")
    print(f"  {'-'*12} {'-'*6} {'-'*24} {'-'*38}")
    for name, cfg in PROVIDERS.items():
        env  = cfg.get("env") or "— (no key needed)"
        free = "✅" if cfg["free"] else "💰"
        print(f"  {name:<12} {free:<7} {env:<24} {cfg['note']}")
    print()


def print_banner() -> None:
    cyan  = "\033[96m"
    bold  = "\033[1m"
    reset = "\033[0m"
    ver   = "\033[93m"
    if not sys.stdout.isatty():
        print(f"readmegen v{__version__} — AI-powered README generator")
        return
    print(f"""
{cyan}{bold}
  ██████╗ ███████╗ █████╗ ██████╗ ███╗   ███╗███████╗ ██████╗ ███████╗███╗   ██╗
  ██╔══██╗██╔════╝██╔══██╗██╔══██╗████╗ ████║██╔════╝██╔════╝ ██╔════╝████╗  ██║
  ██████╔╝█████╗  ███████║██║  ██║██╔████╔██║█████╗  ██║  ███╗█████╗  ██╔██╗ ██║
  ██╔══██╗██╔══╝  ██╔══██║██║  ██║██║╚██╔╝██║██╔══╝  ██║   ██║██╔══╝  ██║╚██╗██║
  ██║  ██║███████╗██║  ██║██████╔╝██║ ╚═╝ ██║███████╗╚██████╔╝███████╗██║ ╚████║
  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═════╝ ╚═╝     ╚═╝╚══════╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝
{reset}  {ver}v{__version__}{reset}  AI-powered README generator  ·  zero dependencies  ·  7 providers
""")

# ══════════════════════════════════════════════════════════════════════════════
# Provider-specific error hints
# ══════════════════════════════════════════════════════════════════════════════

_PROVIDER_ERROR_HINTS: Dict[str, List[str]] = {
    "groq":     ["Check your GROQ_API_KEY at https://console.groq.com"],
    "gemini":   ["Check your GEMINI_API_KEY at https://aistudio.google.com"],
    "deepseek": ["Check your DEEPSEEK_API_KEY at https://platform.deepseek.com"],
    "kimi":     ["Check your KIMI_API_KEY at https://platform.moonshot.cn"],
    "glm":      ["Check your GLM_API_KEY at https://open.bigmodel.cn"],
    "ollama":   ["Start Ollama: ollama serve", "Pull model: ollama pull {model}"],
    "lmstudio": ["Open LM Studio → load a model → start the local server."],
}

# ══════════════════════════════════════════════════════════════════════════════
# CLI entry point
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:  # noqa: C901
    parser = argparse.ArgumentParser(
        description=f"readmegen v{__version__} — AI-powered README generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  readmegen                                  auto-detect provider, current dir
  readmegen ./my-project                     specific repo path
  readmegen --provider groq                  Groq  (needs GROQ_API_KEY)
  readmegen --provider ollama --model mistral
  readmegen --output docs/README.md
  readmegen --stdout                         print to terminal, no file written
  readmegen --dry-run --verbose              prompt preview + token estimate
  readmegen --gen-workflow groq --save-workflow
  readmegen --list-providers
  readmegen --language es                    generate README in Spanish
  readmegen --template my_prompt.md          use custom prompt template
  readmegen --custom-sections "Changelog,FAQ"
  readmegen --backup --overwrite             backup existing README before overwrite
  readmegen --git-context                    include recent git log in prompt
  readmegen --timeout 120                    set API timeout to 120s
  readmegen --max-files 100 --verbose

configuration priority (lowest → highest):
  1. readmegen_defaults.json   (next to this script)
  2. ~/.config/readmegen/config.json  (user-level)
  3. readmegen.json  (per-project, in repo root)
  4. CLI flags  (always win)
        """,
    )

    parser.add_argument("path",              nargs="?", default=".",
                        help="Repository path (default: current directory)")
    parser.add_argument("--provider",        choices=PROVIDER_CHOICES, default=None,
                        help="AI provider (auto-detected if omitted)")
    parser.add_argument("--model",           default=None,
                        help="Model name override")
    parser.add_argument("--base-url",        default=None,
                        help="Override API base URL")
    parser.add_argument("--output",          default=None,
                        help="Output file (default: README.md)")
    parser.add_argument("--stdout",          action="store_true",
                        help="Print README to stdout instead of writing a file")
    parser.add_argument("--overwrite",       action="store_true", default=None,
                        help="Overwrite existing README without prompting")
    parser.add_argument("--backup",          action="store_true", default=None,
                        help="Create .bak before overwriting existing README")
    parser.add_argument("--dry-run",         action="store_true",
                        help="Print prompt preview without calling AI")
    parser.add_argument("--verbose",         action="store_true",
                        help="Show per-file scan stats, config sources, and token estimate")
    parser.add_argument("--language", "-l",  default=None, metavar="LANG",
                        help="Generate README in the specified language (e.g. es, ja)")
    parser.add_argument("--template",        default=None, metavar="FILE",
                        help="Path to a custom prompt template file")
    parser.add_argument("--custom-sections", default=None, metavar="SEC1,SEC2",
                        help="Additional README sections to include")
    parser.add_argument("--git-context",     action="store_true", default=None,
                        help="Include recent git log in the prompt")
    parser.add_argument("--max-files",       type=int, default=None, metavar="N",
                        help=f"Max files to read (default: {DEFAULT_MAX_FILES})")
    parser.add_argument("--max-total-chars", type=int, default=None, metavar="N",
                        help=f"Total char cap (default: {DEFAULT_MAX_TOTAL_CHARS:,})")
    parser.add_argument("--max-file-size",   type=int, default=None, metavar="N",
                        help=f"Per-file char cap (default: {DEFAULT_MAX_FILE_SIZE:,})")
    parser.add_argument("--timeout",         type=int, default=None, metavar="SECS",
                        help="API request timeout in seconds (default: 90, Ollama: 180)")
    parser.add_argument("--gen-workflow",    metavar="PROVIDER",
                        help="Print GitHub Actions YAML for the given provider")
    parser.add_argument("--save-workflow",   action="store_true",
                        help="Save workflow file (use with --gen-workflow)")
    parser.add_argument("--list-providers",  action="store_true",
                        help="List all supported providers and exit")
    parser.add_argument("--version",         action="version",
                        version=f"readmegen {__version__}")
    args = parser.parse_args()

    # ── Info-only commands (no banner, no config) ─────────────────────────────

    if args.list_providers:
        print_providers_table()
        return

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

    # ── Determine repo root ───────────────────────────────────────────────────

    root = Path(args.path).resolve()
    if not root.is_dir():
        print(f"❌ '{root}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    # ══════════════════════════════════════════════════════════════════════════
    # 4-tier config loading
    # ══════════════════════════════════════════════════════════════════════════

    # Tier 1 + 2: Shipped defaults + user-level config
    base_config = load_all_configs(verbose=args.verbose)

    # Tier 3: Project-level config
    project_config = load_project_config(root, verbose=args.verbose)

    # Merge: project overrides base
    merged_config: Dict[str, Any] = {}
    merged_config.update(base_config)
    merged_config.update(project_config)

    # Tier 4: CLI args override everything
    for config_key, arg_name in _CONFIG_ARG_MAP.items():
        if config_key in merged_config and getattr(args, arg_name) is None:
            setattr(args, arg_name, merged_config[config_key])

    # Handle custom_sections (list in JSON → comma string for arg)
    if "custom_sections" in merged_config and args.custom_sections is None:
        cs = merged_config["custom_sections"]
        if isinstance(cs, list) and cs:
            args.custom_sections = ",".join(str(s) for s in cs)
        elif cs:
            args.custom_sections = str(cs)

    # ── Apply hardcoded fallbacks for remaining None values ───────────────────

    args.output          = args.output if args.output is not None else "README.md"
    args.max_files       = args.max_files if args.max_files is not None else DEFAULT_MAX_FILES
    args.max_total_chars = args.max_total_chars if args.max_total_chars is not None else DEFAULT_MAX_TOTAL_CHARS
    args.max_file_size   = args.max_file_size if args.max_file_size is not None else DEFAULT_MAX_FILE_SIZE
    args.overwrite       = bool(args.overwrite) if args.overwrite is not None else False
    args.backup          = bool(args.backup) if args.backup is not None else False
    args.git_context     = bool(args.git_context) if args.git_context is not None else False

    # Validate --timeout
    if args.timeout is not None:
        if args.timeout <= 0 or args.timeout > 600:
            print("❌ --timeout must be between 1 and 600 seconds.", file=sys.stderr)
            sys.exit(1)

    # Validate --provider from config
    if args.provider is not None and args.provider not in PROVIDERS:
        print(
            f"❌ Invalid provider '{args.provider}'. "
            f"Choose from: {', '.join(PROVIDER_CHOICES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    # ── Banner ────────────────────────────────────────────────────────────────

    print_banner()

    # ── [SEC-2] Validate --output early ──────────────────────────────────────

    if not args.stdout:
        try:
            output_path = is_safe_output_path(root, args.output)
        except ValueError as exc:
            print(f"❌ {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        output_path = None  # type: ignore[assignment]

    # ── [SEC-1] Validate --base-url early ────────────────────────────────────

    if args.base_url:
        provider_for_check = args.provider or "ollama"
        try:
            validate_url(args.base_url, require_https=(provider_for_check in CLOUD_PROVIDERS))
        except ValueError as exc:
            print(f"❌ Invalid --base-url: {exc}", file=sys.stderr)
            sys.exit(1)

    # ── Load custom template ──────────────────────────────────────────────────

    template_text: Optional[str] = None
    if args.template:
        tpl_path = Path(args.template).resolve()
        if not tpl_path.is_file():
            print(f"❌ Template file not found: {tpl_path}", file=sys.stderr)
            sys.exit(1)
        try:
            template_text = tpl_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"❌ Cannot read template: {exc}", file=sys.stderr)
            sys.exit(1)
        if args.verbose:
            print(f"⚙️  Loaded template: {tpl_path} ({len(template_text):,} chars)")

    # ── Parse custom sections ─────────────────────────────────────────────────

    custom_sections: Optional[List[str]] = None
    if args.custom_sections:
        custom_sections = [s.strip() for s in args.custom_sections.split(",") if s.strip()]

    # ── Load .readmegenignore ─────────────────────────────────────────────────

    _, _, ignore_count = load_readmegenignore(root)
    if ignore_count and args.verbose:
        print(f"⚙️  Loaded .readmegenignore ({ignore_count} rules)")

    # ── Detect license ────────────────────────────────────────────────────────

    license_id = detect_license(root) if args.verbose or not args.dry_run else None

    # ── Scan ──────────────────────────────────────────────────────────────────

    repo_name = root.name
    print(f"🔍 Scanning: {root}")

    repo_data = scan_repo(
        root,
        max_files      = args.max_files,
        max_total      = args.max_total_chars,
        max_file_size  = args.max_file_size,
        verbose        = args.verbose,
    )

    print(f"📂 {repo_data['total_files_read']} files  ({repo_data['total_chars']:,} chars)")
    if repo_data["skipped_sensitive"]:
        print(f"🔒 {repo_data['skipped_sensitive']} sensitive file(s) skipped")
    print(f"🌳 {len(repo_data['structure'].splitlines())} directory entries")

    if args.verbose and repo_data["lang_counts"]:
        sorted_langs = sorted(repo_data["lang_counts"].items(), key=lambda x: -x[1])
        lang_str = ", ".join(f"{count} {lang}" for lang, count in sorted_langs)
        print(f"📊 Languages: {lang_str}")

    if license_id:
        print(f"📄 License: {license_id} (detected)")

    # ── Git context ───────────────────────────────────────────────────────────

    git_log: Optional[str] = None
    if args.git_context:
        git_log = get_git_log(root)
        if git_log and args.verbose:
            commit_count = len(git_log.splitlines())
            print(f"📜 Included git log ({commit_count} commits)")
        elif args.verbose:
            print("📜 No git history available — skipped git context")

    # ── Build prompt ──────────────────────────────────────────────────────────

    prompt = build_prompt(
        repo_data, repo_name,
        language        = args.language,
        template        = template_text,
        custom_sections = custom_sections,
        git_log         = git_log,
        license_id      = license_id,
    )

    if args.verbose:
        tok = estimate_tokens(prompt)
        print(f"📏 Estimated prompt tokens: ~{tok:,}")
        if tok > 7500:
            print(
                f"⚠️  Token estimate ({tok:,}) is high — consider "
                f"--max-total-chars or --max-files to stay within model limits.",
                file=sys.stderr,
            )

    # ── Dry-run ───────────────────────────────────────────────────────────────

    if args.dry_run:
        safe_prompt = mask_secrets_in_text(prompt)
        print("\n" + "─" * 60)
        print("DRY RUN — Prompt preview (first 3 000 chars, secrets masked):")
        print("─" * 60)
        preview = safe_prompt[:3000]
        print(preview + ("…" if len(safe_prompt) > 3000 else ""))
        print(f"\nFull prompt: {len(prompt):,} chars  (~{estimate_tokens(prompt):,} tokens)")
        return

    # ── Provider resolution ───────────────────────────────────────────────────

    if args.provider:
        provider_name = args.provider
        env_var       = PROVIDERS[provider_name].get("env")
        api_key       = os.getenv(env_var, "") if env_var else ""
    else:
        provider_name, api_key = detect_provider()
        print(f"🤖 Auto-detected provider: {provider_name}")

    cfg     = PROVIDERS[provider_name]
    env_var = cfg.get("env")
    if env_var and not api_key:
        api_key = os.getenv(env_var, "")

    if provider_name in CLOUD_PROVIDERS and env_var and not api_key:
        print(f"\n❌ No API key for '{provider_name}'.")
        print(f"   export {env_var}=your_key_here")
        print(f"   Free key at: {cfg['signup']}")
        sys.exit(1)

    # ── Token-aware trimming ──────────────────────────────────────────────────

    prompt, trimmed_count = trim_prompt_to_limit(
        prompt, repo_data, repo_name, provider_name,
        language        = args.language,
        template        = template_text,
        custom_sections = custom_sections,
        git_log         = git_log,
        license_id      = license_id,
        verbose         = args.verbose,
    )

    # ── Build provider instance ───────────────────────────────────────────────

    try:
        provider = build_provider(
            provider_name, api_key, args.model, args.base_url, args.timeout,
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)

    model_label = provider.model or "(server default)"
    if api_key:
        print(f"🔑 API key: {redact_key(api_key)}")
    print(f"✨ Generating with {provider_name} [{model_label}]…")

    # ── Generate (with retry + latency) ───────────────────────────────────────

    try:
        t0 = time.monotonic()
        readme = call_with_retry(provider, prompt, verbose=args.verbose)
        elapsed = time.monotonic() - t0
    except KeyboardInterrupt:
        print("\n⛔ Cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"❌ HTTP {exc.code}: {body}", file=sys.stderr)
        _print_provider_hints(provider_name, provider.model, is_timeout=False)
        sys.exit(1)
    except urllib.error.URLError as exc:
        is_timeout = "timed out" in str(exc.reason).lower()
        print(f"❌ Connection error: {exc.reason}", file=sys.stderr)
        _print_provider_hints(provider_name, provider.model, is_timeout=is_timeout)
        sys.exit(1)
    except Exception as exc:
        print(f"❌ Unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"✨ Generated in {elapsed:.1f}s")

    readme = clean_readme(readme)
    validate_readme(readme)

    # ── Output ────────────────────────────────────────────────────────────────

    if args.stdout:
        print(readme)
        return

    # ── Diff preview on overwrite ─────────────────────────────────────────────

    if output_path.exists() and not args.overwrite:
        existing = output_path.read_text(encoding="utf-8")
        if sys.stdout.isatty():
            diff_text = show_diff(existing, readme)
            if diff_text:
                print("\n" + "─" * 60)
                print("Diff preview (current → generated):")
                print("─" * 60)
                print(diff_text)
                print("─" * 60)

            ans = input("Overwrite? [y/N/d] ").strip().lower()
            while ans == "d":
                full_diff = show_diff(existing, readme, max_lines=999999)
                if full_diff:
                    print(full_diff)
                else:
                    print("(no differences)")
                ans = input("Overwrite? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                sys.exit(0)
        else:
            ans = input(f"⚠️  '{output_path}' exists. Overwrite? [y/N] ").strip().lower()
            if ans != "y":
                print("Aborted.")
                sys.exit(0)

    # ── Backup existing README ────────────────────────────────────────────────

    if args.backup and output_path.exists():
        bak_path = output_path.with_suffix(output_path.suffix + ".bak")
        bak_path.write_text(output_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"📦 Backup saved to: {bak_path}")

    # ── Write output ──────────────────────────────────────────────────────────

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(readme, encoding="utf-8")

    print(f"\n✅ README written to: {output_path}")
    print(f"   {len(readme):,} chars · {len(readme.splitlines())} lines")
    print(f"\n💡 Set up auto-generation on push:")
    print(f"   python readmegen.py --gen-workflow {provider_name} --save-workflow")


def _print_provider_hints(provider_name: str, model: Optional[str], is_timeout: bool) -> None:
    hints = _PROVIDER_ERROR_HINTS.get(provider_name, [])
    if is_timeout:
        print(f"   The request timed out. Try --timeout 120 for slower models.", file=sys.stderr)
    for hint in hints:
        formatted = hint.replace("{model}", model or "unknown")
        print(f"   {formatted}", file=sys.stderr)
    if not hints and not is_timeout:
        print("   Check your internet connection.", file=sys.stderr)


if __name__ == "__main__":
    main()
