//! fastagent-tauri
//! Drop-in Edge Agent Engine integration for Tauri desktop applications.
//! Provides native Rust commands, sidecar process lifecycle management,
//! and real-time event streaming to Tauri webviews.

use serde::{Deserialize, Serialize};
use std::process::{Child, Command};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{AppHandle, Manager};

#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct FastAgentConfig {
    pub endpoint: String,
    pub model_path: String,
    pub memory_budget_mb: Option<u32>,
    pub port: u16,
}

impl Default for FastAgentConfig {
    fn default() -> Self {
        Self {
            endpoint: "http://127.0.0.1:8085".to_string(),
            model_path: "gemma-2b-q4.gguf".to_string(),
            memory_budget_mb: Some(2048),
            port: 8085,
        }
    }
}

pub struct FastAgentState {
    pub client: reqwest::Client,
    pub config: FastAgentConfig,
    pub child_process: Mutex<Option<Child>>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TurnRequest {
    pub prompt: String,
    pub session_id: Option<String>,
    pub max_tokens: Option<u32>,
    pub grammar: Option<String>,
    pub json_schema: Option<serde_json::Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct TurnResponse {
    pub output: String,
    pub parsed_json: Option<serde_json::Value>,
    pub session_id: String,
    pub prompt_eval_ms: f64,
    pub turn_count: u32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct StatusResponse {
    pub status: String,
    pub model_path: String,
    pub memory: serde_json::Value,
    pub slots: serde_json::Value,
    pub license: serde_json::Value,
}

/// Spawns the FastAgent edge daemon sidecar with parent-PID watchdog.
pub fn spawn_sidecar(binary_path: &str, config: &FastAgentConfig) -> std::io::Result<Child> {
    let parent_pid = std::process::id();
    let mut cmd = Command::new(binary_path);
    cmd.arg("serve")
        .arg("--model").arg(&config.model_path)
        .arg("--port").arg(config.port.to_string())
        .arg("--parent-pid").arg(parent_pid.to_string());

    if let Some(budget) = config.memory_budget_mb {
        cmd.arg("--memory-budget-mb").arg(budget.to_string());
    }

    cmd.spawn()
}

/// Tauri Command: Runs single turn with slot caching.
#[tauri::command]
pub async fn fastagent_turn(
    request: TurnRequest,
    state: tauri::State<'_, FastAgentState>,
) -> Result<TurnResponse, String> {
    let url = format!("{}/v1/agent/turn", state.config.endpoint);
    let payload = serde_json::json!({
        "prompt": request.prompt,
        "session_id": request.session_id.unwrap_or_else(|| "default".to_string()),
        "max_tokens": request.max_tokens.unwrap_or(160),
        "grammar": request.grammar,
        "json_schema": request.json_schema,
    });

    let resp = state
        .client
        .post(&url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("HTTP request error: {}", e))?;

    if !resp.status().is_success() {
        return Err(format!("Engine error: HTTP {}", resp.status()));
    }

    resp.json::<TurnResponse>()
        .await
        .map_err(|e| format!("Failed to parse response: {}", e))
}

/// Tauri Command: Runs multi-step autonomous agent.
#[tauri::command]
pub async fn fastagent_ask(
    prompt: String,
    session_id: Option<String>,
    state: tauri::State<'_, FastAgentState>,
) -> Result<String, String> {
    let url = format!("{}/v1/agent/ask", state.config.endpoint);
    let payload = serde_json::json!({
        "prompt": prompt,
        "session_id": session_id.unwrap_or_else(|| "default".to_string()),
        "max_steps": 5,
    });

    let resp = state
        .client
        .post(&url)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("HTTP error: {}", e))?;

    let body: serde_json::Value = resp
        .json()
        .await
        .map_err(|e| format!("Parse error: {}", e))?;

    Ok(body["result"].as_str().unwrap_or("").to_string())
}

/// Tauri Command: Query engine status, RAM metrics, and active slots.
#[tauri::command]
pub async fn fastagent_status(
    state: tauri::State<'_, FastAgentState>,
) -> Result<StatusResponse, String> {
    let url = format!("{}/v1/status", state.config.endpoint);
    let resp = state
        .client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("HTTP error: {}", e))?;

    resp.json::<StatusResponse>()
        .await
        .map_err(|e| format!("Parse error: {}", e))
}
