import os
import psutil
import streamlit as st
from fast_agent import (
    find_llama_server,
    MemoryBudgetManager,
    ModelManager,
    EDGE_MODEL_CATALOG,
    LicenseManager,
)

st.set_page_config(page_title="FastAgent Edge Engine Wizard", page_icon="⚡", layout="wide")

st.title("⚡ FastAgent: Embeddable Edge Agent Engine")
st.markdown(
    "Diagnostic dashboard and configuration wizard for desktop applications (Electron, Tauri, Flutter). "
    "Verify hardware readiness, dynamic memory budgets, slot caching, and offline licenses."
)

tab_hw, tab_models, tab_license, tab_quickstart = st.tabs([
    "1. Hardware & Memory Budget",
    "2. Curated Edge Models",
    "3. Licensing & Monetization",
    "4. Desktop App Quickstart",
])

with tab_hw:
    st.header("Hardware Readiness & Memory Ceiling")
    mem_mgr = MemoryBudgetManager()
    metrics = mem_mgr.get_system_snapshot()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total System RAM", f"{metrics['total_system_ram_mb']} MB")
    c2.metric("Available System RAM", f"{metrics['available_system_ram_mb']} MB")
    c3.metric("Recommended Budget", f"{metrics['engine_budget_mb']} MB")
    c4.metric("Memory Pressure", f"{metrics['system_ram_used_percent']}%")

    st.subheader("Binary Discovery")
    try:
        server_path = find_llama_server()
        st.success(f"✅ Core C++ Engine binary found at: `{server_path}`")
    except FileNotFoundError:
        server_path = None
        st.error("❌ `llama-server` executable not found. Please extract binaries into workspace or PATH.")

with tab_models:
    st.header("Curated Edge Model Catalog")
    st.markdown("Quantized models optimized for consumer PCs (8GB RAM laptops, edge devices).")

    cols = st.columns(len(EDGE_MODEL_CATALOG))
    for i, (m_id, meta) in enumerate(EDGE_MODEL_CATALOG.items()):
        with cols[i]:
            st.markdown(f"### {meta['name']}")
            st.markdown(f"**Size:** {meta['size_mb']} MB")
            st.markdown(f"**Min RAM:** {meta['min_ram_mb']} MB")
            st.markdown(f"**Best For:** {meta['ideal_for']}")
            st.caption(f"Context: {meta['recommended_context']} tokens")

    st.divider()
    st.subheader("Discovered Local Models")
    local_models = ModelManager.find_local_models()
    if local_models:
        for m in local_models:
            st.write(f"📁 **{m['filename']}** ({m['size_mb']} MB) - `{m['path']}`")
    else:
        st.info("No local `.gguf` models found. Use the CLI `fastagent-edge models download qwen2.5-1.5b`.")

with tab_license:
    st.header("Offline Licensing & Monetization")
    st.markdown(
        "FastAgent uses a dual-licensing model: **Free Community Edition** for open-source / solo developers, "
        "and **Commercial Developer Licenses** with cryptographically signed offline tokens for proprietary desktop apps."
    )

    token_input = st.text_input("Enter License Token (or leave blank for Community Edition):")
    lic = LicenseManager.verify_license(token_input)

    l_col1, l_col2, l_col3 = st.columns(3)
    l_col1.metric("License Tier", lic.tier)
    l_col2.metric("Licensee", lic.licensee)
    l_col3.metric("Max Concurrent Slots", lic.max_concurrent_slots)

    if lic.is_valid:
        st.success(f"Status: {lic.message}")
    else:
        st.warning(f"Status: {lic.message}")

with tab_quickstart:
    st.header("Drop-In Integration Code")
    st.markdown("Choose your desktop framework to view drop-in integration code:")

    fw = st.radio("Framework", ["Electron / Node.js", "Tauri / Rust", "Flutter / Dart", "Python Desktop (PyQt)"], horizontal=True)

    if fw == "Electron / Node.js":
        st.code('''const { FastAgentDaemonProcess, FastAgentClient } = require('@fastagent/edge-sdk');

// 1. Spawns headless edge daemon bound to Electron parent process
const daemon = new FastAgentDaemonProcess({
  modelPath: 'models/qwen2.5-1.5b-instruct-q4_k_m.gguf',
  memoryBudgetMb: 2048, // 2GB ceiling (no OOMs on 8GB laptops)
});

await daemon.start();
const client = new FastAgentClient();

// 2. Multi-tab slot caching
const tab = client.session('tab-editor-1');
await tab.stream("Summarize active file", (token) => {
  webContents.send('ai:token', token);
});''', language="javascript")

    elif fw == "Tauri / Rust":
        st.code('''// In src-tauri/src/main.rs
use fastagent_tauri::{FastAgentConfig, FastAgentState, spawn_sidecar, fastagent_turn, fastagent_ask};

let config = FastAgentConfig {
    endpoint: "http://127.0.0.1:8085".into(),
    model_path: "qwen2.5-1.5b-instruct-q4_k_m.gguf".into(),
    memory_budget_mb: Some(2048),
    port: 8085,
};

let child = spawn_sidecar("fastagent-edge", &config)?;''', language="rust")

    elif fw == "Flutter / Dart":
        st.code('''import 'package:fast_agent_edge/fast_agent_edge.dart';

final client = FastAgentClient(baseUrl: 'http://127.0.0.1:8085');

// Stream completion to Flutter UI
final session = client.session('document-tab-1');
session.stream("Generate meeting action items").listen((token) {
  setState(() => responseText += token);
});''', language="dart")

    else:
        st.code('''from fast_agent import FastAgent, MemoryBudgetManager, SlotCacheManager

agent = FastAgent(model_path="gemma-2b-q4.gguf", memory_budget_mb=2048)
response = agent.ask("Multiply 36 by 12 and format as JSON.")''', language="python")
