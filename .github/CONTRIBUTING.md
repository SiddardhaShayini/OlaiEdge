# Contributing to OlaiEdge

Thank you for your interest in contributing to **OlaiEdge** (*Optimizing Local AI at the Edge*)!

OlaiEdge is an embeddable, headless edge agent engine designed for desktop applications (Electron, Tauri, Flutter, and native frameworks). Our mission is to give every desktop software developer the ability to embed offline, zero-latency, private AI agents into their software without crashing consumer hardware with Out-Of-Memory (OOM) errors.

---

## Table of Contents

- [Core Principles](#core-principles)
- [Development Setup](#development-setup)
- [Project Architecture Map](#project-architecture-map)
- [How to Contribute](#how-to-contribute)
  - [Adding Desktop Grammar Schemas](#adding-desktop-grammar-schemas)
  - [Enhancing Desktop Framework SDKs](#enhancing-desktop-framework-sdks)
  - [Reporting Bugs](#reporting-bugs)
  - [Suggesting Enhancements](#suggesting-enhancements)
- [Testing & Quality Assurance](#testing--quality-assurance)
- [Pull Request Workflow](#pull-request-workflow)
- [Code of Conduct](#code-of-conduct)

---

## Core Principles

Every pull request and contribution to OlaiEdge must adhere to these non-negotiable architectural tenets:

1. **Zero-Overhead Philosophy:** OlaiEdge targets highly constrained consumer edge machines (CPU-only, 8 GB RAM). We never introduce heavy Python dependencies when lightweight or standard library alternatives suffice.
2. **Crash-Proof Memory Safety:** Code changes must never cause unbounded RAM consumption. All allocations must respect the configured `MemoryBudgetManager` ceiling.
3. **Sub-100ms TTFT:** The Longest Common Prefix (LCP) cache pinning must be preserved so time-to-first-token remains under 75ms on CPU.
4. **Execution Safety:** Never execute model outputs via `eval()`. Tool calling must strictly use AST literals (`safe_parse_args`) and validated JSON schemas.
5. **Deterministic Output:** Structured tasks must always provide GBNF grammar logit masking to prevent malformed syntax.

---

## Development Setup

### 1. Prerequisites

- **Python:** 3.9, 3.10, 3.11, or 3.12.
- **Git:** Latest version.
- **C++ Engine:** The package includes pre-compiled C++ engine binaries inside `olaiedge/_engine/`. If running on Linux or macOS, install `llama-server` via system package manager or build from llama.cpp.

### 2. Fork and Clone

```bash
git clone https://github.com/<your-username>/OlaiEdge.git
cd OlaiEdge
```

### 3. Create a Virtual Environment

```bash
# On Linux/macOS
python3 -m venv venv
source venv/bin/activate

# On Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### 4. Install Dependencies in Editable Mode

```bash
pip install -e ".[all]"
```

This installs:
- Core runtime dependencies (`requests`, `psutil`)
- Diagnostic wizard (`streamlit`)
- Web search tools (`duckduckgo-search`)
- Testing framework (`pytest`)

### 5. Download a Lightweight Test Model

Use the built-in zero-dependency helper to fetch a fast 1.5B test model:

```bash
python olai.py models download qwen2.5-1.5b
```

---

## Project Architecture Map

```
OlaiEdge/
├── olaiedge/                           # Core Engine Package
│   ├── __init__.py                     # Clean package exports
│   ├── core.py                         # OlaiEngine: KV cache, LCP reuse, tool loop
│   ├── daemon.py                       # Headless REST/SSE HTTP daemon (olai serve)
│   ├── memory_manager.py               # MemoryBudgetManager: RAM monitoring & OOM circuit breaker
│   ├── slot_manager.py                 # SlotCacheManager: Multi-tab LCP slot reuse & LRU
│   ├── grammar_engine.py               # GBNF compiler & pre-packaged desktop schemas
│   ├── model_catalog.py                # Curated edge models & background downloader
│   ├── license_manager.py              # Dual-licensing & offline cryptographic verification
│   ├── cli.py                          # 'olai' CLI entrypoints
│   └── _engine/                        # Internal C++ binary encapsulation
│
├── sdks/                               # Desktop Framework Bridges
│   ├── electron-node/                  # @olaiedge/sdk (Node.js & Electron)
│   ├── tauri-rust/                     # olaiedge-tauri (Rust crate with Tauri commands)
│   ├── flutter-dart/                   # olaiedge_flutter (Dart client with Stream<String>)
│   └── python-desktop/                 # PyQt/PySide non-blocking Qt worker thread
│
├── examples/                           # Desktop Integration Examples
│   └── desktop_app_example.py          # Multi-tab code editor / note-taking demo
│
└── tests/                              # Comprehensive Unit Test Suite
    ├── test_olaiedge.py                # OlaiEngine core, memory budgets, slot tests
    ├── test_edge_engine.py             # Daemon routes, SSE streaming, GBNF schemas
    └── test_fast_agent.py              # Backward compatibility tests
```

---

## How to Contribute

### Adding Desktop Grammar Schemas

If your desktop app belongs to a vertical not yet covered (e.g., Vector Graphics/SVG, Audio/DAW automation, GIS, Game Development), you can add a pre-packaged schema to `olaiedge/grammar_engine.py`:

1. Define the schema in `DESKTOP_SCHEMAS`:
   ```python
   "audio_daw_patch": {
       "type": "object",
       "properties": {
           "track_id": {"type": "integer"},
           "fx_chain": {"type": "array", "items": {"type": "string"}},
           "volume_db": {"type": "number"},
           "pan": {"type": "number"},
       },
       "required": ["track_id", "volume_db"],
   }
   ```
2. Add a corresponding unit test in `tests/test_edge_engine.py`.
3. Submit your PR!

### Enhancing Desktop Framework SDKs

We welcome improvements to:
- **Electron:** Enhancing `@olaiedge/sdk` with TypeScript definitions or child-process lifecycle features.
- **Tauri:** Updating `olaiedge-tauri` for Tauri v2 compatibility and state management.
- **Flutter:** Improving `olaiedge_flutter` stream transformers and Flutter desktop lifecycle hooks.
- **Native Bridges:** Adding C#, Go, or Swift bindings for native Windows/macOS desktop apps.

---

## Testing & Quality Assurance

Before submitting any code, verify that all tests pass locally:

```bash
# Run complete test suite
pytest

# Run hardware diagnostic eval
python olai.py eval

# Run desktop integration demo
python examples/desktop_app_example.py
```

All 26 unit tests must pass with zero regressions.

---

## Pull Request Workflow

1. **Create a Topic Branch:**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```
2. **Commit Your Changes:**
   Write clear, concise commit messages following Conventional Commits (e.g., `feat: add audio DAW grammar schema`, `fix: handle socket timeout in daemon watchdog`).
3. **Push to Your Fork:**
   ```bash
   git push origin feature/your-feature-name
   ```
4. **Open a Pull Request:**
   - Link any relevant issues.
   - Describe what changed and why.
   - Attach test output proving zero regressions.

---

## Code of Conduct

All contributors and maintainers are expected to follow our [Code of Conduct](CODE_OF_CONDUCT.md). Please be respectful, inclusive, and professional in all interactions.

## Questions?

Feel free to open a [GitHub Discussion](https://github.com/SiddardhaShayini/OlaiEdge/discussions) or contact the lead maintainer:
- **Siddardha Shayini** (siddardhashayini9@gmail.com)
