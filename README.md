# 🤖 readmeGen

> AI-powered README generator — scan any repo, get professional documentation instantly.

![Version](https://img.shields.io/badge/version-0.3.1-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![Dependencies](https://img.shields.io/badge/dependencies-zero-success)
![License](https://img.shields.io/badge/license-MIT-blue)

**Zero pip dependencies · Pure Python stdlib · 7 AI providers · Security hardened**

![readmegen banner](preview.png)

---

## ✨ Features
 
- 🔍 **Deep repo scanning** — reads file tree, source, configs, manifests; smart file prioritization including AI instruction files (`.cursorrules`, `CLAUDE.md`, etc.)
- 🧠 **Understands your stack** — generates contextual, accurate documentation with license detection and optional git history context
- 🌐 **7 AI providers** — 5 cloud free tiers + 2 fully local options
- ⚙️ **GitHub Actions** — one command to wire up auto-regeneration on every push
- 🔒 **Security hardened** — SSRF prevention, path traversal blocking, symlink guards, sensitive file detection with glob patterns, API key redaction, TLS certificate enforcement
- 🏗️ **Provider abstraction** — clean OOP architecture; adding a new backend takes one class
- 🔁 **Smart retry** — exponential backoff with `Retry-After` header respect on HTTP 429
- 📏 **Token-aware trimming** — automatically drops low-priority files when a prompt exceeds a provider's context window
- 🌍 **Multi-language output** — generate READMEs in any language with `--language`
- 📝 **Custom templates** — bring your own prompt template with `{{REPO_NAME}}`, `{{STRUCTURE}}`, `{{FILES_SECTION}}` placeholders
- 📊 **Rich verbose mode** — language stats, per-file skip reasons, scan progress, config source tracing
- 🔀 **Diff preview** — see a unified diff before overwriting an existing README
- 📦 **Backup on overwrite** — automatically create `.bak` before replacing
- 🛡️ **Secret masking in dry-run** — never leaks env values in prompt previews
- 📦 **Zero dependencies** — pure Python stdlib, works anywhere Python 3.8+ is installed
- ⚙️ **4-tier configuration** — shipped defaults → user config → per-project config → CLI flags
---
 
## 🌐 Supported AI Providers
 
| Provider     | Env Variable         | Free? | Default Model         | Context Limit  | Get Key |
|--------------|----------------------|-------|-----------------------|----------------|---------|
| **groq**     | `GROQ_API_KEY`       | ✅    | llama3-70b-8192       | ~28k tokens    | [console.groq.com](https://console.groq.com) |
| **gemini**   | `GEMINI_API_KEY`     | ✅    | gemini-1.5-flash      | ~900k tokens   | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **deepseek** | `DEEPSEEK_API_KEY`   | ✅    | deepseek-chat         | ~56k tokens    | [platform.deepseek.com](https://platform.deepseek.com) |
| **kimi**     | `KIMI_API_KEY`       | ✅    | moonshot-v1-8k        | ~7k tokens     | [platform.moonshot.cn](https://platform.moonshot.cn) |
| **glm**      | `GLM_API_KEY`        | ✅    | glm-4-flash           | ~110k tokens   | [open.bigmodel.cn](https://open.bigmodel.cn) |
| **ollama**   | *(none)*             | ✅    | llama3                | ~28k tokens    | [ollama.com](https://ollama.com) |
| **lmstudio** | *(none)*             | ✅    | *(your loaded model)* | ~28k tokens    | [lmstudio.ai](https://lmstudio.ai) |
 
**Auto-detection order:** groq → gemini → deepseek → kimi → glm → lmstudio → ollama
 
---
 
## 🚀 Quick Start
 
```bash
# 1. Download (no install needed)
curl -O https://raw.githubusercontent.com/nasaomar165/readmegen/main/readmegen.py
curl -O https://raw.githubusercontent.com/nasaomar165/readmegen/main/readmegen_defaults.json
 
# 2. Set your preferred provider in readmegen_defaults.json (edit once, applies everywhere)
#    Or set a free API key:
export GROQ_API_KEY=your_key_here
 
# 3. Run on your project
python readmegen.py /path/to/your/repo
```
 
---
 
## 📖 Usage
 
```bash
# Auto-detect provider, current directory
python readmegen.py
 
# Specific repo path
python readmegen.py ./my-project
 
# Choose a cloud provider
python readmegen.py --provider groq
python readmegen.py --provider deepseek
python readmegen.py --provider kimi
python readmegen.py --provider glm
python readmegen.py --provider gemini
 
# Local models — no API key needed
python readmegen.py --provider ollama
python readmegen.py --provider ollama --model mistral
python readmegen.py --provider lmstudio
python readmegen.py --provider lmstudio --base-url http://192.168.1.5:1234
 
# Output options
python readmegen.py --output docs/README.md    # custom file path
python readmegen.py --stdout                   # print to terminal, no file written
python readmegen.py --overwrite                # skip confirmation prompt
python readmegen.py --backup --overwrite       # backup existing README before overwriting
 
# Multi-language output
python readmegen.py --language es              # generate README in Spanish
python readmegen.py --language ja              # generate README in Japanese
python readmegen.py -l fr                      # short flag
 
# Custom prompt template
python readmegen.py --template my_prompt.md
 
# Extra README sections
python readmegen.py --custom-sections "Changelog,FAQ,Benchmarks"
 
# Git context — include recent commit history in the prompt
python readmegen.py --git-context
 
# Timeout control
python readmegen.py --timeout 120              # 120 second API timeout
 
# Overwrite with diff preview
python readmegen.py                            # shows unified diff, asks [y/N/d]
                                               # d = show full diff, then ask again
 
# Debugging & inspection
python readmegen.py --dry-run                  # prompt preview (secrets masked)
python readmegen.py --dry-run --verbose        # preview + token estimate + language stats
python readmegen.py --list-providers           # show all providers
 
# Fine-grained scan control
python readmegen.py --max-files 100
python readmegen.py --max-total-chars 160000
python readmegen.py --max-file-size 25000
python readmegen.py --max-files 100 --max-total-chars 160000 --verbose
 
# GitHub Actions
python readmegen.py --gen-workflow groq                 # print YAML to stdout
python readmegen.py --gen-workflow groq --save-workflow # save to .github/workflows/readme.yml
```
 
---
 
## ⚙️ GitHub Actions — Auto-regenerate README on push
 
One command wires readmegen into your CI:
 
```bash
python readmegen.py --gen-workflow groq --save-workflow
```
 
This creates `.github/workflows/readme.yml`. On every push to `main`, GitHub Actions will:
 
1. Check out the repository
2. Run `readmegen` with your chosen provider
3. Commit and push the updated `README.md` automatically
**Setup:**
1. Go to **Settings → Secrets and variables → Actions**
2. Add the secret for your provider (e.g. `GROQ_API_KEY`)
3. Push — runs on every subsequent commit
> ⚠️ Local providers (Ollama, LM Studio) cannot run in GitHub Actions. Use any cloud provider instead.
 
---
 
## ⚙️ Configuration — 4-Tier Priority System
 
Set your preferences once and forget them. Each tier overrides the one above it:
 
| Priority | Source | File | Purpose |
|----------|--------|------|---------|
| 1 (lowest) | Shipped defaults | `readmegen_defaults.json` (next to script) | Edit once — your preferred provider, model, flags |
| 2 | User-level | `~/.config/readmegen/config.json` | Personal overrides across all projects |
| 3 | Project-level | `readmegen.json` (in repo root) | Per-project settings (e.g., `--language ja`) |
| 4 (highest) | CLI flags | Command line | Always win over all config files |
 
### Example: `readmegen_defaults.json`
 
Edit this file once after downloading — it ships next to `readmegen.py`:
 
```json
{
  "_doc": "Edit this file once to set your preferred defaults. CLI flags always override these values.",
 
  "provider": "groq",
  "model": "llama3-70b-8192",
  "overwrite": true,
  "backup": true,
  "verbose": true,
  "max_files": 80,
  "max_total_chars": 120000,
  "timeout": 120
}
```
 
After this, `python readmegen.py ./any-project` just works — no flags needed.
 
### Example: per-project `readmegen.json`
 
Drop this in a repo root for project-specific overrides (commit it or `.gitignore` it):
 
```json
{
  "language": "ja",
  "custom_sections": ["Changelog", "Architecture Decision Records"],
  "git_context": true,
  "max_files": 120
}
```
 
### Example: user-level `~/.config/readmegen/config.json`
 
Your personal preferences that follow you across every project:
 
```json
{
  "backup": true,
  "verbose": true,
  "timeout": 120
}
```
 
Keys starting with `_` (like `"_doc"`) are treated as comments and ignored.
 
Use `--verbose` to see exactly which config files were loaded:
 
```
⚙️  Loaded shipped defaults: /home/user/tools/readmegen_defaults.json
⚙️  Loaded user config: /home/user/.config/readmegen/config.json
⚙️  Loaded project config: /home/user/my-project/readmegen.json
```
 
---
 
## 🚫 `.readmegenignore`
 
Works exactly like `.gitignore` — place it in the repo root:
 
```
# Skip heavy generated directories
vendor/
generated/
docs/examples/
 
# Skip test fixtures
tests/fixtures/
*.snap
 
# Skip specific files
CHANGELOG.md
```
 
Lines ending in `/` are treated as directory patterns. Use `--verbose` to confirm:
 
```
⚙️  Loaded .readmegenignore (5 rules)
⚠️  Skip vendor: ignored directory (vendor)
```
 
---
 
## 🔒 Security
 
All protections run automatically — no configuration required.
 
### SEC-1 — SSRF & URL Scheme Validation
 
`--base-url` and all provider URLs are validated before any network call. Only `http://` and `https://` schemes are accepted. `file://`, `ftp://`, `javascript:`, `data:` and all others are rejected. Cloud providers additionally require HTTPS.
 
```
❌  --base-url file:///etc/passwd     blocked (disallowed scheme)
❌  --base-url ftp://evil.com         blocked (disallowed scheme)
❌  --base-url http://api.groq.com    blocked (cloud requires HTTPS)
✅  --base-url https://api.groq.com   allowed
✅  --base-url http://localhost:11434  allowed (local)
```
 
### SEC-2 — Output Path Traversal Prevention
 
`--output` paths are resolved and verified to stay inside the repository root before any write occurs.
 
```
❌  --output ../../etc/crontab   blocked (escapes root)
❌  --output /etc/passwd         blocked (absolute path outside root)
✅  --output docs/README.md      allowed
```
 
### SEC-3 — Symlink Escape & Sensitive File Blocking
 
Every file discovered by `rglob("*")` has its symlink-resolved real path checked to confirm it stays inside the repository root. Files that commonly hold secrets are blocked via both an exact name set and `fnmatch` glob patterns — case-insensitively:
 
| Type | Examples |
|------|---------|
| Exact names | `.env`, `id_rsa`, `id_ed25519`, `.netrc`, `auth.json`, … |
| Glob: crypto files | `*.pem`, `*.key`, `*.crt`, `*.p12`, `*.pfx` |
| Glob: secrets files | `secrets.*`, `credentials.*`, `password.*` |
| Glob: env variants | `.env.*` (`.env.local`, `.env.production`, …) |
 
Skipped files are counted and reported — never silently dropped.
 
### SEC-4 — Secret Masking & Key Redaction
 
`--dry-run` automatically applies regex masking before displaying any prompt output, replacing assignments like `API_KEY=abc123` with `API_KEY=[REDACTED]`. API keys are also never printed in full — only the first and last 4 characters are shown:
 
```
🔑 API key: sk-a…cdef
```
 
### SEC-5 — Specific Exception Handling
 
All file-read errors are caught as `OSError` (not a bare `except`) and printed to stderr, so permission errors and broken symlinks are visible instead of silently swallowed.
 
### SEC-6 — TLS Certificate Verification
 
Every outbound request explicitly uses `ssl.create_default_context()`. There is no `ssl.CERT_NONE` or certificate verification bypass anywhere in the codebase.
 
---
 
## 🏗️ Architecture
 
### Provider Abstraction
 
Providers are a clean class hierarchy. Adding a new AI backend means writing one class:
 
```
BaseProvider  (abc.ABC)
├── OpenAICompatProvider   ← Groq, DeepSeek, Kimi, GLM, LM Studio
├── GeminiProvider         ← Google Gemini
└── OllamaProvider         ← Ollama local server
```
 
### Smart Retry with `Retry-After`
 
Transient failures (HTTP 429, 500–504, network errors) are retried automatically. On HTTP 429, the `Retry-After` header is respected (parsed as integer seconds or HTTP date), falling back to exponential backoff:
 
```
HTTP 429 + Retry-After: 10  →  wait 10s (capped at 60s)
HTTP 502                    →  wait 1s → 2s → 4s → raise
Network timeout             →  wait 1s → 2s → 4s → raise
```
 
### Token-Aware Prompt Trimming
 
Each provider has a configured context limit. If the estimated prompt tokens exceed it, readmegen automatically removes the lowest-priority files one by one and rebuilds the prompt until it fits:
 
```
Estimated tokens: ~35,000 (exceeds Groq ~28k limit)
⚠️  Trimmed 4 file(s) to fit token limit (~27,800 tokens)
✨ Generating with groq [llama3-70b-8192]…
```
 
Priority files (e.g., `package.json`, `main.py`, `Dockerfile`) are kept until last.
 
### How a scan works
 
```
Your repo
    │
    ▼
Load config (4 tiers: defaults → user → project → CLI)
    │
    ▼
Load .readmegenignore (if present)
    │
    ▼
Scan recursively (rglob)
    │  skip dirs:  node_modules, .git, __pycache__, dist, venv, ...  + .readmegenignore rules
    │  skip files: *.pyc, *.lock, .DS_Store, ...                     + .readmegenignore rules
    │  skip:       symlinks escaping root
    │  skip:       .env, *.key, secrets.*, credentials.*, *.pem, ...
    │  prioritize: package.json, main.py, go.mod, Dockerfile,
    │             .cursorrules, CLAUDE.md, copilot-instructions.md, ...
    │  truncate:   at last newline before --max-file-size (not mid-line)
    │  caps:       --max-files (50)  ·  --max-total-chars (80,000)
    │              --max-file-size (15,000 per file)
    ▼
Detect license (MIT, Apache-2.0, GPL-3.0, BSD, ISC, ...)
    │
    ▼
[Optional] Read git log (--git-context)
    │
    ▼
Validate security constraints
    │  --output path stays inside repo root        [SEC-2]
    │  --base-url uses http/https only             [SEC-1]
    ▼
Build structured prompt
    │  directory tree + file contents + license hint + git log
    │  --language: instruction to write in target language
    │  --template: custom prompt with {{REPO_NAME}}, {{STRUCTURE}}, {{FILES_SECTION}}
    │  --custom-sections: additional section headings
    │  token-aware trimming if over provider limit
    │  --dry-run: mask secrets before display      [SEC-4]
    ▼
Call AI provider (with smart retry)
    │  cloud (HTTPS + cert verification):  Groq, Gemini, DeepSeek, Kimi, GLM
    │  local:                              Ollama, LM Studio
    │  --timeout: user-configurable request timeout
    ▼
Validate AI response
    │  warn if < 200 chars (possible failure)
    │  warn if no Markdown headings found
    ▼
Write README.md  (or --stdout)
    │  [Optional] show unified diff before overwrite
    │  [Optional] create .bak backup
    │  path traversal check before write           [SEC-2]
    ▼
Report latency ("Generated in 3.2s")
    │
    ▼
Optional: GitHub Actions commits README on every push
```
 
---
 
## 🛠️ Configuration Reference
 
### CLI Flags
 
| Flag | Default | Description |
|------|---------|-------------|
| `path` | `.` | Repository path |
| `--provider` | auto | AI provider to use |
| `--model` | per-provider | Override model name |
| `--base-url` | per-provider | Override API endpoint URL |
| `--output` | `README.md` | Output file path |
| `--stdout` | off | Print to terminal instead of file |
| `--overwrite` | off | Skip overwrite confirmation |
| `--backup` | off | Create `.bak` before overwriting |
| `--dry-run` | off | Preview prompt, no AI call |
| `--verbose` | off | Language stats, skip reasons, progress, config sources, token estimate |
| `--language`, `-l` | English | Generate README in specified language |
| `--template` | — | Path to custom prompt template file |
| `--custom-sections` | — | Comma-separated extra sections (e.g. `"Changelog,FAQ"`) |
| `--git-context` | off | Include recent git log in the prompt |
| `--timeout` | 90 (180 for Ollama) | API request timeout in seconds (1–600) |
| `--max-files` | 50 | Maximum files to read |
| `--max-total-chars` | 80,000 | Total character cap for prompt |
| `--max-file-size` | 15,000 | Per-file character cap (truncates at last newline) |
| `--gen-workflow` | — | Print GitHub Actions YAML for a provider |
| `--save-workflow` | off | Save workflow (use with `--gen-workflow`) |
| `--list-providers` | — | Show all providers and exit |
| `--version` | — | Print version and exit |
 
### Config File Keys
 
All keys below work in `readmegen_defaults.json`, `~/.config/readmegen/config.json`, and `readmegen.json`:
 
| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `provider` | string | null | AI provider name |
| `model` | string | null | Model name override |
| `base_url` | string | null | API endpoint override |
| `output` | string | `"README.md"` | Output file path |
| `language` | string | null | Target language |
| `timeout` | int | null | Request timeout (seconds) |
| `max_files` | int | 50 | Max files to scan |
| `max_total_chars` | int | 80000 | Total character cap |
| `max_file_size` | int | 15000 | Per-file character cap |
| `overwrite` | bool | false | Skip confirmation |
| `backup` | bool | false | Backup before overwrite |
| `git_context` | bool | false | Include git log |
| `custom_sections` | list | `[]` | Extra section names |
 
### Environment Variables
 
| Variable | Provider |
|----------|----------|
| `GROQ_API_KEY` | Groq |
| `GEMINI_API_KEY` | Google Gemini |
| `DEEPSEEK_API_KEY` | DeepSeek |
| `KIMI_API_KEY` | Kimi (Moonshot) |
| `GLM_API_KEY` | Zhipu GLM |
| `XDG_CONFIG_HOME` | Overrides `~/.config` location for user config |
 
---
 
## 🔧 Install as a global CLI (optional)
 
```bash
pip install -e .
# Use from anywhere:
readmegen ./my-project
readmegen --provider deepseek --verbose ./my-project
```
 
---
 
## 📋 Project Structure
 
```
readmegen/
├── readmegen.py               # entire tool — single file, zero deps
├── readmegen_defaults.json    # shipped defaults — edit once, applies everywhere
├── pyproject.toml             # optional: install as 'readmegen' CLI
├── README.md                  # this file
└── .github/
    └── workflows/
        └── readme.yml         # example GitHub Actions workflow
```
 
---
 
## 🗂️ Changelog
 
### v0.3.1 — Configuration system
- **4-tier config loading**: shipped defaults (`readmegen_defaults.json`) → user config (`~/.config/readmegen/config.json`) → project config (`readmegen.json`) → CLI flags
- **`readmegen_defaults.json`**: ships next to the script — set your provider/model once, never type flags again
- **XDG-compliant user config**: respects `XDG_CONFIG_HOME`, defaults to `~/.config/readmegen/config.json`
- **Config source tracing**: `--verbose` shows exactly which config files were loaded
- **Comment keys**: JSON keys starting with `_` are ignored (e.g. `"_doc": "..."`)
### v0.3.0 — Major feature release (22 improvements)
 
**New flags:**
- `--language` / `-l` — generate README in any language
- `--template` — custom prompt template with `{{REPO_NAME}}`, `{{STRUCTURE}}`, `{{FILES_SECTION}}` placeholders
- `--custom-sections` — append extra README sections (e.g. `"Changelog,FAQ"`)
- `--backup` — create `.bak` before overwriting
- `--git-context` — include recent git log in the prompt
- `--timeout` — user-configurable API timeout (1–600s)
**New features:**
- `.readmegenignore` support (gitignore-style, directory-aware)
- Diff preview on overwrite — unified diff with `[y/N/d]` prompt (`d` shows full diff)
- Token-aware prompt trimming — automatically drops files exceeding provider context limits
- License file detection — identifies MIT, Apache-2.0, GPL-3.0, BSD, ISC, MPL-2.0, Unlicense, 0BSD
- AI response validation — warns if output is suspiciously short or missing Markdown headings
- File type statistics in `--verbose` (e.g. `📊 Languages: 12 Python, 5 TypeScript, 3 YAML`)
- Scan progress indicator in `--verbose`
- Provider latency reporting (`✨ Generated in 3.2s`)
- Graceful `KeyboardInterrupt` handling (exit code 130, clean message)
- Provider-specific error hints for all 7 providers
**Improvements:**
- Smarter file truncation — cuts at last newline before limit, not mid-line
- Additional priority files — `.cursorrules`, `CLAUDE.md`, `copilot-instructions.md`, `.windsurfrules`, `.gemini/rules`
- Verbose skip reasons — logs why every file was skipped (sensitive, ignored, symlink, unreadable)
- `Retry-After` header parsing on HTTP 429 (integer or HTTP date, capped at 60s)
- Per-provider context limits in provider registry (used for auto-trimming)
**Bug fix:**
- Fixed duplicate ASCII banner printing on normal runs
### v0.2.2 — Architecture & UX improvements
- Provider abstraction: `BaseProvider` ABC with `OpenAICompatProvider`, `GeminiProvider`, `OllamaProvider`
- Exponential backoff retry: automatic retry on HTTP 429/5xx and network errors (1s → 2s → 4s)
- Token estimation: `--verbose` shows `~N tokens` and warns if the model context window may be exceeded
- Secret masking in dry-run: `API_KEY=abc123` → `API_KEY=[REDACTED]`
- Expanded sensitive file detection: `*.pem`, `*.key`, `*.crt`, `secrets.*`, `credentials.*`, `password.*`, `.env.*`
- Case-insensitive ignore matching: works identically on Windows, macOS, Linux
- ASCII art banner: colorful intro on normal runs
- New CLI flags: `--verbose`, `--stdout`, `--max-files`, `--max-total-chars`, `--max-file-size`
### v0.2.1 — Security hardening
- SEC-1: SSRF / URL scheme validation
- SEC-2: Output path traversal prevention
- SEC-3: Symlink escape guard + sensitive file blocklist
- SEC-4: API key redaction in all output
- SEC-5: Replaced bare `except` with `OSError`
- SEC-6: Explicit TLS certificate verification
### v0.2.0 — New providers & GitHub Actions
- Added DeepSeek, Kimi (Moonshot), GLM (Zhipu), LM Studio
- `--gen-workflow` / `--save-workflow` for GitHub Actions
- `--list-providers`, `--base-url`, `--version` flags
- Auto-detection order with LM Studio probe
### v0.1.0 — Initial release
- Groq, Google Gemini, Ollama
- Repo scanning with smart file prioritization
- Single-file, zero-dependency design
---
 
## 🤝 Contributing
 
1. Fork the repository
2. Make changes to `readmegen.py`
3. Test: `python readmegen.py --dry-run --verbose .`
4. Open a pull request
**Please keep the zero-dependency constraint** — stdlib only, no `pip install`.
 
---
 
## 📄 License
 
MIT
