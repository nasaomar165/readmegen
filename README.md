# 🤖 readmegen

> AI-powered README generator — scan any repo, get professional documentation instantly.

![Version](https://img.shields.io/badge/version-0.2.1-blue)
![Python](https://img.shields.io/badge/python-3.8%2B-brightgreen)
![Dependencies](https://img.shields.io/badge/dependencies-zero-success)
![License](https://img.shields.io/badge/license-MIT-blue)

**Zero pip dependencies · Pure Python stdlib · 7 AI providers · Security hardened**

![readmegen banner](preview.png)

---

## ✨ Features

- 🔍 **Deep repo scanning** — reads file tree, source files, configs, and manifests
- 🧠 **Understands your stack** — generates contextual, accurate documentation
- 🌐 **7 AI providers** — 5 cloud free tiers + 2 fully local options
- ⚙️ **GitHub Actions** — one command to wire up auto-regeneration on every push
- 🔒 **Security hardened** — SSRF protection, path traversal prevention, symlink guards, secret file blocking, API key redaction, TLS verification
- 📦 **Zero dependencies** — pure Python 3.8+ stdlib, works anywhere
- ⚡ **Smart file prioritization** — reads `package.json`, `main.py`, `go.mod`, `Dockerfile` first

---

## 🌐 Supported AI Providers

| Provider     | Env Variable         | Free? | Default Model         | Get Key |
|--------------|----------------------|-------|-----------------------|---------|
| **groq**     | `GROQ_API_KEY`       | ✅    | llama3-70b-8192       | [console.groq.com](https://console.groq.com) |
| **gemini**   | `GEMINI_API_KEY`     | ✅    | gemini-1.5-flash      | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| **deepseek** | `DEEPSEEK_API_KEY`   | ✅    | deepseek-chat         | [platform.deepseek.com](https://platform.deepseek.com) |
| **kimi**     | `KIMI_API_KEY`       | ✅    | moonshot-v1-8k        | [platform.moonshot.cn](https://platform.moonshot.cn) |
| **glm**      | `GLM_API_KEY`        | ✅    | glm-4-flash           | [open.bigmodel.cn](https://open.bigmodel.cn) |
| **ollama**   | *(none)*             | ✅    | llama3                | [ollama.com](https://ollama.com) |
| **lmstudio** | *(none)*             | ✅    | *(your loaded model)* | [lmstudio.ai](https://lmstudio.ai) |

**Auto-detection order:** groq → gemini → deepseek → kimi → glm → lmstudio → ollama

---

## 🚀 Quick Start

```bash
# 1. Download (no install needed)
curl -O https://raw.githubusercontent.com/nasaomar165/readmegen/main/readmegen.py

# 2. Set a free API key
export GROQ_API_KEY=your_key_here

# 3. Run on your project
python readmegen.py /path/to/your/repo
```

---

## 📖 Usage

```bash
# Auto-detect provider, current directory
python readmegen.py

# Specify a repo
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
python readmegen.py --output docs/README.md    # custom output path
python readmegen.py --overwrite                # skip confirmation

# Inspect & debug
python readmegen.py --dry-run                  # preview prompt, no AI call
python readmegen.py --list-providers           # show all providers

# GitHub Actions
python readmegen.py --gen-workflow groq                 # print YAML to stdout
python readmegen.py --gen-workflow groq --save-workflow # save to .github/workflows/readme.yml
```

---

## ⚙️ GitHub Actions — Auto-regenerate README on push

Wire readmegen into CI with a single command:

```bash
python readmegen.py --gen-workflow groq --save-workflow
```

This creates `.github/workflows/readme.yml`. On every push to `main`, the workflow will:

1. Check out the repository
2. Run `readmegen` with your chosen provider
3. Commit and push the updated `README.md` automatically

**Setup steps:**

1. Go to your repo → **Settings → Secrets and variables → Actions**
2. Add the secret for your provider (e.g. `GROQ_API_KEY`)
3. Push — it runs on every subsequent commit

> ⚠️ Local providers (Ollama, LM Studio) cannot run in GitHub Actions. Use any cloud provider instead.

---

## 🔒 Security

Version 0.2.1 introduced a full security hardening pass. All protections run automatically with no configuration needed.

### SEC-1 — SSRF & URL Scheme Validation
`--base-url` is validated before any request is made. Only `http://` and `https://` schemes are accepted. `file://`, `ftp://`, `javascript:` and all other schemes are rejected. Cloud providers additionally enforce HTTPS.

```
❌  --base-url file:///etc/passwd     → blocked (disallowed scheme)
❌  --base-url ftp://evil.com         → blocked (disallowed scheme)
❌  --base-url http://api.groq.com    → blocked (cloud requires HTTPS)
✅  --base-url https://api.groq.com   → allowed
✅  --base-url http://localhost:11434  → allowed (local)
```

### SEC-2 — Output Path Traversal Prevention
`--output` paths are resolved and verified to stay inside the repository root before any file is written.

```
❌  --output ../../etc/crontab   → blocked (escapes root)
❌  --output /etc/passwd         → blocked (absolute outside root)
✅  --output docs/README.md      → allowed
```

### SEC-3 — Symlink Escape & Sensitive File Blocking
`rglob("*")` follows symlinks, so a crafted repo could use `ln -s /etc/passwd leak.txt` to exfiltrate host files to the AI. readmegen resolves every symlink and verifies the real path is still inside the repository root before reading it.

Additionally, files that commonly contain secrets are never read:

```
.env  .env.*  id_rsa  id_ed25519  .netrc  .npmrc
secrets.yml  credentials  auth.json  (and more)
```

Skipped sensitive files are counted and reported — never silently ignored.

### SEC-4 — API Key Redaction
API keys are never printed in full. All output shows only the first and last 4 characters:

```
🔑 Using API key: sk-a…cdef
```

### SEC-5 — Specific Exception Handling
File read errors are caught as `OSError` (not bare `except`) and reported to stderr, so permission errors and broken symlinks are visible rather than silently swallowed.

### SEC-6 — TLS Certificate Verification
All outbound requests use `ssl.create_default_context()`, ensuring certificate verification is always enforced. There is no `ssl.CERT_NONE` anywhere in the codebase.

---

## 🛠️ Configuration Reference

| Flag / Env Var        | Description |
|-----------------------|-------------|
| `--provider`          | AI provider to use (auto-detected if omitted) |
| `--model`             | Override the default model name |
| `--base-url`          | Override API URL (remote Ollama, custom LM Studio host) |
| `--output`            | Output file path (default: `README.md`) |
| `--overwrite`         | Skip the overwrite confirmation prompt |
| `--dry-run`           | Preview the prompt without calling AI |
| `--gen-workflow`      | Print GitHub Actions YAML for a given provider |
| `--save-workflow`     | Save the workflow file (use with `--gen-workflow`) |
| `--list-providers`    | Print all providers with env vars and notes |
| `--version`           | Print version and exit |
| `GROQ_API_KEY`        | API key for Groq |
| `GEMINI_API_KEY`      | API key for Google Gemini |
| `DEEPSEEK_API_KEY`    | API key for DeepSeek |
| `KIMI_API_KEY`        | API key for Kimi (Moonshot) |
| `GLM_API_KEY`         | API key for Zhipu GLM |

---

## 🔧 Install as a global CLI (optional)

```bash
pip install -e .
# Use from anywhere:
readmegen ./my-project
readmegen --provider deepseek ./my-project
```

---

## 🏗️ How It Works

```
Your repo
    │
    ▼
Scan recursively
    │  skip:      node_modules, .git, __pycache__, dist, venv, ...
    │  skip:      .env, id_rsa, secrets.yml, and other sensitive files
    │  skip:      symlinks that escape the repo root
    │  prioritize: package.json, main.py, go.mod, Dockerfile, ...
    │  cap:        50 files · 80,000 chars total
    ▼
Validate security constraints
    │  --output path stays inside repo root
    │  --base-url uses http/https only
    ▼
Build structured prompt
    │  directory tree + file contents
    ▼
Call chosen AI provider
    │  cloud (HTTPS + cert verification): Groq, Gemini, DeepSeek, Kimi, GLM
    │  local: Ollama, LM Studio
    ▼
Write README.md
    │  title, features, install, usage, config,
    │  project structure, API reference, contributing, license
    ▼
Optional: GitHub Actions commits README on every push
```

---

## 📋 Project Structure

```
readmegen/
├── readmegen.py               # entire tool — single file, zero deps
├── pyproject.toml             # optional: install as 'readmegen' CLI
├── README.md                  # this file
└── .github/
    └── workflows/
        └── readme.yml         # example GitHub Actions workflow
```

---

## 🗂️ Changelog

### v0.2.1 — Security hardening
- SEC-1: SSRF / URL scheme validation for `--base-url`
- SEC-2: Output path traversal prevention
- SEC-3: Symlink escape guard + sensitive file blocklist (`.env`, `id_rsa`, etc.)
- SEC-4: API key redaction in all log output
- SEC-5: Replaced bare `except` with specific `OSError` handling
- SEC-6: Explicit TLS certificate verification on all requests

### v0.2.0 — New providers & GitHub Actions
- Added DeepSeek, Kimi (Moonshot), GLM (Zhipu) providers
- Added LM Studio local provider
- Added `--gen-workflow` / `--save-workflow` for GitHub Actions
- Added `--list-providers`, `--base-url`, `--version` flags
- Auto-detection probes LM Studio before falling back to Ollama

### v0.1.0 — Initial release
- Groq, Google Gemini, Ollama providers
- Repo scanning with smart file prioritization
- Single-file, zero-dependency design

---

## 🤝 Contributing

1. Fork the repo
2. Make your changes in `readmegen.py`
3. Test: `python readmegen.py --dry-run .`
4. Open a pull request

Please keep the zero-dependency constraint — stdlib only.

---

## 📄 License

MIT
