# olaiedge-tauri

Native Rust crate for integrating the OlaiEdge Agent Engine into Tauri desktop applications.

## Features

- **Tauri Sidecar Integration:** Spawns `olai` as a managed sidecar binary with `--parent-pid` auto-cleanup.
- **Tauri Commands:** Drop-in `#[tauri::command]` handlers for `fastagent_turn`, `fastagent_ask`, and `fastagent_status`.
- **Slot Caching per Webview Window:** Multiple Tauri windows/tabs map directly to isolated OlaiEdge slots.
- **Zero Cloud Costs & Zero OOMs:** Strict memory budgeting.

## Integration in `src-tauri/src/main.rs`

```rust
use olaiedge_tauri::{fastagent_ask, fastagent_turn, fastagent_status, FastAgentConfig, FastAgentState, spawn_sidecar};
use std::sync::Mutex;

fn main() {
    let config = FastAgentConfig {
        endpoint: "http://127.0.0.1:8085".to_string(),
        model_path: "qwen2.5-1.5b-instruct-q4_k_m.gguf".to_string(),
        memory_budget_mb: Some(2048),
        port: 8085,
    };

    // Spawn sidecar daemon
    let child = spawn_sidecar("olai", &config).expect("Failed to start OlaiEdge daemon");

    tauri::Builder::default()
        .manage(FastAgentState {
            client: reqwest::Client::new(),
            config,
            child_process: Mutex::new(Some(child)),
        })
        .invoke_handler(tauri::generate_handler![
            fastagent_turn,
            fastagent_ask,
            fastagent_status
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

## Calling from Frontend (React / Svelte / Vue)

```typescript
import { invoke } from '@tauri-apps/api/tauri';

// Execute turn in active tab slot
const response = await invoke('fastagent_turn', {
  request: {
    prompt: "Summarize this CAD document",
    sessionId: "cad-tab-3"
  }
});

console.log(response.output);
console.log(`Latency: ${response.prompt_eval_ms} ms`);
```
