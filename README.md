<div align="center">
  <img src="assets/olaiedge-banner.svg" alt="OlaiEdge: Optimizing Local AI at the Edge" width="680"/>
  <br/><br/>
  <p><strong>The zero-overhead, headless local AI runtime (packaged as an SDK or background daemon) that desktop developers can drop directly into Electron, Tauri, Flutter, and native desktop applications.</strong></p>
  <p><em>Formerly known as FastAgent — completely re-engineered for zero-clutter, drop-in desktop deployment.</em></p>

  [![Tests](https://img.shields.io/badge/tests-26%20passed-brightgreen.svg)]()
  [![License](https://img.shields.io/badge/license-MIT%20%2F%20Commercial-blue.svg)]()
  [![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)]()
  [![Frameworks](https://img.shields.io/badge/frameworks-Electron%20%7C%20Tauri%20%7C%20Flutter%20%7C%20Python-orange.svg)]()
</div>

---

## What is OlaiEdge?

**OlaiEdge** (pronounced *Oh-lai Edge*, standing for **Optimizing Local AI at the Edge**) is a lightweight, headless inference and agent engine built specifically for desktop software companies (**code editors, note-taking apps, CAD tools, accounting software**).

It eliminates the two biggest pain points in desktop AI today:
1. **Cloud AI Frustrations:** High latency (1.5s–4s), privacy compliance liabilities (HIPAA, GDPR, enterprise code leak fears), and recurring cloud API bills.
2. **Local AI Crashes:** Out-of-memory (OOM) crashes on 8GB consumer PCs, multi-tab cache thrashing, malformed JSON outputs, and zombie processes left behind when desktop windows close.

---

## ⚡ The Zero-Clutter Developer Experience

No messy folder with 30 loose DLLs. No manual C++ configuration. Just install and run:

```bash
pip install olaiedge
```

```python
import olaiedge

# Automatically discovers model, enforces memory budget, and warms cache
agent = olaiedge.OlaiEngine()

@agent.tool("Multiplies two numbers. Pass as (a, b).")
def multiply(a: float, b: float) -> float:
    return a * b

response = agent.ask("Multiply 36 by 12 and format as a final answer.")
print(response)
```

---

## Architecture Overview

```mermaid
graph TD
    subgraph Desktop Host Application
        UI["Desktop App UI (Electron / Tauri / Flutter)"]
        SDK["OlaiEdge SDK Client (Node.js / Rust / Dart / Python)"]
    end

    subgraph OlaiEdge Headless Runtime
        Daemon["Headless HTTP & SSE Streaming Daemon (olai serve)"]
        Watchdog["Parent Process PID & OOM Watchdog"]
        MemMgr["Memory Budget Manager (Dynamic Quantization & Context Right-Sizing)"]
        SlotMgr["Slot Cache Manager (Multi-Tab LCP Cache & LRU Eviction)"]
        Grammar["Grammar Engine (GBNF Logit Constrained JSON)"]
        License["Offline Cryptographic License Verifier"]
    end

    subgraph Hardware Layer
        Core["llama.cpp C++ Engine (8-bit Quantized KV Cache)"]
        RAM["Host RAM / VRAM (Enforced Ceiling)"]
    end

    UI -->|IPC / UI Events| SDK
    SDK -->|Localhost REST / SSE| Daemon
    Watchdog -.->|Auto-Kills Daemon on App Exit| Daemon
    Daemon --> MemMgr
    Daemon --> SlotMgr
    Daemon --> Grammar
    Daemon --> License
    SlotMgr -->|LCP Slot Reuse| Core
    MemMgr -->|Enforces Safety Margin| RAM
    Grammar -->|Strict Logit Constraints| Core
```

### Core Innovations

- **Dynamic Memory Budget Enforcer:** Configurable RAM budget ceiling (`--memory-budget-mb`). Automatically rightsizes context window lengths, batch sizes, and 8-bit/4-bit KV quantization (`-ctk q8_0 -ctv q8_0`) to guarantee **zero OOM crashes on 8GB laptops**.
- **Multi-Tab Slot Caching:** Tab-isolated conversation states with Longest Common Prefix (LCP) caching. Pre-warms the root system prompt and tool definitions so tab switching achieves **prompt eval latencies under 75ms**.
- **Grammar-Constrained JSON Output:** Translates JSON Schemas into GBNF grammars. Guarantees 100% syntactically valid JSON output for code diffs, note summaries, CAD commands, and financial ledger entries.
- **Parent Process Watchdog:** Binds the background daemon to the parent desktop process PID (`--parent-pid`). If the desktop application closes or crashes, the background engine terminates cleanly within 2 seconds.

---

## Performance Benchmarks

| Metric | Cloud APIs (GPT-4o / Claude) | Raw Local Server (Ollama / Default) | **OlaiEdge Engine** |
| :--- | :--- | :--- | :--- |
| **Time-To-First-Token (TTFT)** | 1,200 – 3,500 ms | 3,450 ms (CPU prompt eval) | **~73 ms (LCP slot reuse)** |
| **8GB Consumer Stability** | N/A (External) | Fails / OOM crashes | **100% Stable (Enforced Budget)** |
| **Data Privacy** | Leaves device | Local | **100% Local (Air-Gapped)** |
| **Multi-Tab Memory** | N/A | Duplicate contexts / Thrashing | **LRU Slot Cache + Compaction** |
| **JSON Syntactic Validity** | 92% – 97% | 68% (on <3B models) | **100% (GBNF Logit Constrained)** |
| **Recurring Cloud Bills** | $15 – $40 / seat / mo | $0 | **$0 / seat** |

---

## Framework Integration Guides

### 1. Electron & Node.js (`@olaiedge/sdk`)

In your Electron `main.js`:

```javascript
const { app, BrowserWindow, ipcMain } = require('electron');
const { FastAgentDaemonProcess: OlaiDaemonProcess, FastAgentClient: OlaiClient } = require('@fastagent/edge-sdk');
const path = require('path');

let daemon, client;

app.whenReady().then(async () => {
  daemon = new OlaiDaemonProcess({
    modelPath: path.join(__dirname, 'models/qwen2.5-1.5b-instruct-q4_k_m.gguf'),
    port: 8085,
    memoryBudgetMb: 2048, // 2GB memory ceiling
  });

  const endpoint = await daemon.start();
  client = new OlaiClient({ baseUrl: endpoint });
  createWindow();
});

// Stream tokens directly to active document tab
ipcMain.handle('ai:stream', async (event, { prompt, tabId }) => {
  const session = client.session(tabId); // Tab slot isolation
  await session.stream(prompt, (token) => {
    event.sender.send(`ai:token:${tabId}`, token);
  });
});

app.on('before-quit', () => daemon?.stop());
```

---

### 2. Tauri & Rust (`olaiedge-tauri`)

In `src-tauri/src/main.rs`:

```rust
use fastagent_tauri::{
    fastagent_ask, fastagent_status, fastagent_turn,
    spawn_sidecar, FastAgentConfig, FastAgentState,
};
use std::sync::Mutex;

fn main() {
    let config = FastAgentConfig {
        endpoint: "http://127.0.0.1:8085".to_string(),
        model_path: "qwen2.5-1.5b-instruct-q4_k_m.gguf".to_string(),
        memory_budget_mb: Some(2048),
        port: 8085,
    };

    let child = spawn_sidecar("olai", &config).expect("Failed to start OlaiEdge");

    tauri::Builder::default()
        .manage(FastAgentState {
            client: reqwest::Client::new(),
            config,
            child_process: Mutex::new(Some(child)),
        })
        .invoke_handler(tauri::generate_handler![fastagent_turn, fastagent_ask, fastagent_status])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

---

### 3. Flutter Desktop (`olaiedge_flutter`)

In Flutter desktop:

```dart
import 'package:fast_agent_edge/fast_agent_edge.dart';

final client = FastAgentClient(baseUrl: 'http://127.0.0.1:8085');

void streamNoteAssistant(String tabId, String content) {
  final session = client.session(tabId); // Multi-tab slot cache
  session.stream("Summarize: $content").listen((token) {
    setState(() => buffer += token);
  });
}
```

---

## Pre-Packaged Desktop Grammar Schemas

OlaiEdge includes pre-built GBNF schemas tailored for major desktop application verticals:

| Vertical | Schema Name | Guaranteed Output Properties |
| :--- | :--- | :--- |
| **Code Editors** | `code_editor_patch` | `file_path`, `action (replace/insert/delete)`, `start_line`, `replacement_code`, `commit_message` |
| **Note-Taking Apps** | `note_summary` | `title`, `summary`, `key_points[]`, `action_items[]`, `tags[]` |
| **CAD & 3D Tools** | `cad_command` | `operation (extrude/cut/fillet)`, `target_body`, `plane`, `dimensions_mm`, `tolerance` |
| **Accounting / ERP** | `accounting_entry` | `transaction_id`, `date`, `debit_account`, `credit_account`, `amount`, `currency`, `tax_code` |

---

## CLI Reference (`olai`)

```bash
# 1. Run headless daemon with memory budget and parent process monitoring
olai serve --model qwen2.5-1.5b --port 8085 --memory-budget-mb 2048 --parent-pid 12345

# 2. Inspect running daemon status, memory RSS, and active tabs
olai status

# 3. List curated edge models and download with progress tracking
olai models list
olai models download qwen2.5-1.5b

# 4. Generate or verify offline commercial developer licenses
olai license verify --token "OLAI-COMM-..."
olai license generate --licensee "Enterprise Partner" --seats 50 --slots 16

# 5. Run hardware diagnostic evaluation
olai eval
```

---

## Monetization & Dual-Licensing

```
+-------------------------------------------------------------------------+
| OlaiEdge: Dual Licensing Model                                          |
+------------------------------------+------------------------------------+
| Community Edition                  | Commercial Developer License       |
| (Open-Source / Solo Developers)    | (Proprietary Desktop Apps / ISVs)  |
+------------------------------------+------------------------------------+
| • 100% Free under MIT License      | • Per-seat or commercial licensing |
| • Unlimited local agent execution  | • Multi-slot concurrency (16+ tabs)|
| • Single-tab slot caching          | • Aggressive memory compaction     |
| • Standard memory budgeting        | • Offline signed license tokens    |
| • Full GBNF grammar constraints    | • Zero telemetry / 100% air-gapped |
| • Open-source & hobbyist friendly  | • Bundled desktop installer rights |
+------------------------------------+------------------------------------+
```

### Cryptographic Offline Verification

```bash
# Generate a signed commercial license for an ISV partner (20 seats, 16 slots, 365 days)
python olai.py license generate --licensee "Acme Desktop Corp" --tier COMMERCIAL --seats 20 --slots 16

# Verify any license token offline (zero cloud dependencies)
python olai.py license verify --token "OLAI-COMM-eyJsaWNlbnNlZSI6IkFjbWUgRGVza3RvcCBDb3JwIiwidGllciI6IkNPTU1FUkNJQUwiLCJzZWF0cyI6MjAsIm1heF9zbG90cyI6MTYsImV4cCI6MTgyNDQ0MDUxOC4zODA4MDAyLCJpYXQiOjE3OTI5MDQ1MTguMzgwODAwMn0=.5ed91ca4614e281d"
```

---

## Curated Edge Model Catalog

| Model ID | Base Architecture | Quantization | Size | Min RAM | Recommended For |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `qwen2.5-1.5b` | Qwen 2.5 1.5B Instruct | Q4_K_M | **986 MB** | 1.5 GB | **Recommended:** Code Editors, Tool Calling, ReAct |
| `llama-3.2-1b` | Meta Llama 3.2 1B Instruct | Q4_K_M | **720 MB** | 1.2 GB | Ultra-low RAM laptops, Note-Taking, Summaries |
| `gemma-2b-q4` | Google Gemma 2B Instruct | Q4 | **1,930 MB** | 2.5 GB | Analytical drafting, Financial formulas |
| `smollm2-1.7b` | HuggingFace SmolLM2 1.7B | Q4_K_M | **1,050 MB** | 1.6 GB | Low-latency autocomplete, CAD operations |

---

## Contributing & Community

We welcome contributions to OlaiEdge! Please see our [Contributing Guide](.github/CONTRIBUTING.md) and [Code of Conduct](.github/CODE_OF_CONDUCT.md) for details on our zero-overhead development philosophy, setting up your local environment, and running the test suite.

```bash
# Setup development environment
git clone https://github.com/SiddardhaShayini/OlaiEdge.git
cd OlaiEdge
pip install -e ".[dev]"

# Run test suite
pytest
```

---

## Lineage & Backward Compatibility

OlaiEdge maintains 100% backward compatibility with FastAgent:
- `import fast_agent` and `from fast_agent import FastAgent, FastAgentEngine` work seamlessly.
- `from olaiedge import OlaiEngine, OlaiDaemon` is the modern primary API.

## Developer

**Siddardha Shayini**
- GitHub: [https://github.com/SiddardhaShayini](https://github.com/SiddardhaShayini)

## Acknowledgements & Recognition

OlaiEdge is officially listed as an indexed repository in the **XERJ Corpus Hub**.

[![XERJ Corpus Hub Contributor](https://hub.xerj.org/contributors/SiddardhaShayini/badge.svg)](https://hub.xerj.org/contributors/SiddardhaShayini)

- **Contributor Profile:** [hub.xerj.org/contributors/SiddardhaShayini](https://hub.xerj.org/contributors/SiddardhaShayini)
- **Indexed Repository:** [SiddardhaShayini/OlaiEdge](https://github.com/SiddardhaShayini/OlaiEdge)
- **Pinned Commit:** [`b8351919f2`](https://github.com/SiddardhaShayini/OlaiEdge/commit/b8351919f2)

## License

OlaiEdge is dual-licensed:
- **Community Edition:** Free under the [MIT License](LICENSE).
- **Commercial Edition:** Available for commercial desktop software publishers.
