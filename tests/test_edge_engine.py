"""
Comprehensive unit tests for FastAgent Edge Agent Engine.
Tests memory budgeting, multi-tab slot caching, GBNF grammar engine,
cryptographic offline licensing, and daemon HTTP endpoints.
"""
import json
import os
import time
import pytest

from fast_agent import (
    MemoryBudgetManager,
    MemoryPressureWarning,
    SlotCacheManager,
    SessionSlot,
    GrammarEngine,
    DESKTOP_SCHEMAS,
    LicenseManager,
    FastAgentLicense,
    LicenseTier,
    ModelManager,
    EDGE_MODEL_CATALOG,
    safe_parse_args,
)


# ============================================================================
# 1. Memory Budget and Crash Prevention Tests
# ============================================================================

def test_memory_budget_calculation():
    # Tight budget: 1GB budget with 800MB model -> forces q4_0, small context
    mgr_tight = MemoryBudgetManager(budget_mb=1024)
    params_tight = mgr_tight.compute_optimal_engine_params(model_size_mb=800, desired_context=2048)
    assert params_tight["ctk"] == "q4_0"
    assert params_tight["ctv"] == "q4_0"
    assert params_tight["context_size"] <= 1024

    # Ample budget: 4GB budget with 1GB model -> optimal q8_0, 2048 context
    mgr_ample = MemoryBudgetManager(budget_mb=4096)
    params_ample = mgr_ample.compute_optimal_engine_params(model_size_mb=1000, desired_context=4096)
    assert params_ample["ctk"] == "q8_0"
    assert params_ample["ctv"] == "q8_0"
    assert params_ample["context_size"] == 4096


def test_memory_snapshot_and_watchdog():
    mgr = MemoryBudgetManager(budget_mb=2048)
    snapshot = mgr.get_system_snapshot()
    assert "total_system_ram_mb" in snapshot
    assert "available_system_ram_mb" in snapshot
    assert snapshot["engine_budget_mb"] == 2048
    assert snapshot["total_system_ram_mb"] > 0


def test_circuit_breaker_on_memory_pressure():
    # Simulate an engine whose budget is heavily exceeded
    mgr = MemoryBudgetManager(budget_mb=10) # Unrealistic 10MB budget
    # The host process itself is > 10MB RSS
    with pytest.raises(MemoryPressureWarning) as exc_info:
        mgr.check_headroom_or_raise()
    assert "Memory budget exceeded" in str(exc_info.value) or "circuit breaker" in str(exc_info.value)


# ============================================================================
# 2. Multi-Tab Slot Caching Tests
# ============================================================================

def test_slot_cache_manager_tab_isolation():
    manager = SlotCacheManager(max_active_slots=3, default_history_turns=4)
    manager.set_pinned_system_prompt("System: You are an Edge Desktop Assistant.")

    # Tab 1: Code editor
    slot_code = manager.get_or_create_slot("tab-code-editor")
    slot_code.add_user_turn("Refactor function multiply()")
    slot_code.append_agent_turn("Thought: Refactoring.\nFinal Answer: Done.")

    # Tab 2: Note taking
    slot_notes = manager.get_or_create_slot("tab-notes")
    slot_notes.add_user_turn("Summarize chapter 1")
    slot_notes.append_agent_turn("Summary: Chapter 1 discusses edge AI.")

    # Verify tab isolation
    prompt_code = manager.build_slot_prompt("tab-code-editor")
    assert "Refactor function multiply()" in prompt_code
    assert "Summarize chapter 1" not in prompt_code
    assert "System: You are an Edge Desktop Assistant." in prompt_code

    prompt_notes = manager.build_slot_prompt("tab-notes")
    assert "Summarize chapter 1" in prompt_notes
    assert "Refactor function multiply()" not in prompt_notes


def test_slot_lru_eviction_and_restoration():
    manager = SlotCacheManager(max_active_slots=2)
    manager.get_or_create_slot("tab-1").add_user_turn("Hello 1")
    manager.get_or_create_slot("tab-2").add_user_turn("Hello 2")
    assert manager.active_slot_count() == 2

    # Accessing 3rd slot must evict LRU slot (tab-1) to archive
    manager.get_or_create_slot("tab-3").add_user_turn("Hello 3")
    assert manager.active_slot_count() == 2
    assert "tab-1" in manager.evicted_slots_archive

    # Re-accessing tab-1 must restore its conversation history from archive
    restored_tab1 = manager.get_or_create_slot("tab-1")
    assert any("Hello 1" in turn for turn in restored_tab1.conversation_history)


def test_slot_compaction_on_memory_pressure():
    manager = SlotCacheManager(max_active_slots=2, default_history_turns=6)
    slot = manager.get_or_create_slot("tab-long")
    for i in range(6):
        slot.add_user_turn(f"Turn {i}")
        slot.append_agent_turn(f"Response {i}")

    assert len(slot.conversation_history) == 6

    # Trigger emergency compaction
    manager.compact_all_slots(keep_last_n_turns=2)
    assert len(slot.conversation_history) == 2


# ============================================================================
# 3. Grammar Engine & Desktop Schemas Tests
# ============================================================================

def test_desktop_schemas_exist():
    for category in ["code_editor_patch", "note_summary", "cad_command", "accounting_entry"]:
        schema = GrammarEngine.get_desktop_schema(category)
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


def test_json_schema_to_gbnf_conversion():
    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["replace", "insert"]},
            "count": {"type": "integer"},
            "valid": {"type": "boolean"},
        },
        "required": ["action", "count"],
    }
    gbnf = GrammarEngine.json_schema_to_gbnf(schema)
    assert "root ::=" in gbnf
    assert '"\\"replace\\""' in gbnf
    assert '"\\"insert\\""' in gbnf
    assert "integer ::=" in gbnf


def test_grammar_validate_and_parse():
    schema = GrammarEngine.get_desktop_schema("code_editor_patch")

    valid_json = json.dumps({
        "file_path": "src/main.rs",
        "action": "replace",
        "start_line": 42,
        "replacement_code": "fn new_logic() {}",
        "commit_message": "Update logic"
    })
    ok, parsed, err = GrammarEngine.validate_and_parse(valid_json, schema)
    assert ok is True
    assert parsed["action"] == "replace"
    assert err is None

    # Missing required field 'replacement_code'
    invalid_json = json.dumps({
        "file_path": "src/main.rs",
        "action": "replace",
        "start_line": 42
    })
    ok, parsed, err = GrammarEngine.validate_and_parse(invalid_json, schema)
    assert ok is False
    assert "Missing required fields" in err


# ============================================================================
# 4. Licensing & Monetization Tests
# ============================================================================

def test_community_edition_license():
    lic = LicenseManager.verify_license(None)
    assert lic.tier == LicenseTier.COMMUNITY
    assert lic.is_valid is True
    assert lic.seat_count == 1
    assert lic.max_concurrent_slots >= 1


def test_commercial_license_token_generation_and_verification():
    token = LicenseManager.generate_token(
        licensee="Acme Desktop Software",
        tier=LicenseTier.COMMERCIAL,
        seat_count=50,
        max_slots=16,
        validity_days=30,
    )
    assert token.startswith("FA-COMM-")

    # Offline verification
    lic = LicenseManager.verify_license(token)
    assert lic.tier == LicenseTier.COMMERCIAL
    assert lic.licensee == "Acme Desktop Software"
    assert lic.seat_count == 50
    assert lic.max_concurrent_slots == 16
    assert lic.is_valid is True


def test_tampered_license_reverts_to_community():
    token = LicenseManager.generate_token(licensee="Legit Corp")
    tampered_token = token[:-4] + "dead"
    lic = LicenseManager.verify_license(tampered_token)
    assert lic.tier == LicenseTier.COMMUNITY
    assert lic.is_valid is False
    assert "mismatch" in lic.message.lower()


# ============================================================================
# 6. Daemon HTTP Server Route Tests (In-Memory Handler Verification)
# ============================================================================

def test_daemon_http_server_endpoints():
    import io
    from fast_agent_pkg.fast_agent.daemon import EdgeDaemonHandler

    class MockDaemon:
        def __init__(self):
            self.model_path = "gemma-2b-q4.gguf"
            self.slot_manager = SlotCacheManager(max_active_slots=4)
            self.license = LicenseManager.verify_license(None)

        def get_status(self):
            return {
                "status": "ready",
                "model_path": self.model_path,
                "memory": {"engine_rss_mb": 500, "engine_budget_mb": 2048},
                "slots": {"active_count": self.slot_manager.active_slot_count(), "max_allowed": 4},
                "license": self.license.to_dict(),
            }

    mock_daemon = MockDaemon()
    EdgeDaemonHandler.daemon_instance = mock_daemon

    def call_handler(method: str, path: str, body: dict = None):
        handler = EdgeDaemonHandler.__new__(EdgeDaemonHandler)
        handler.path = path
        handler.wfile = io.BytesIO()
        encoded_body = json.dumps(body).encode("utf-8") if body else b""
        handler.rfile = io.BytesIO(encoded_body)
        handler.headers = {"Content-Length": str(len(encoded_body))}

        status_codes = []
        sent_headers = {}

        def mock_send_response(code):
            status_codes.append(code)

        def mock_send_header(k, v):
            sent_headers[k] = v

        def mock_end_headers():
            pass

        handler.send_response = mock_send_response
        handler.send_header = mock_send_header
        handler.end_headers = mock_end_headers

        if method == "GET":
            handler.do_GET()
        elif method == "POST":
            handler.do_POST()

        raw_output = handler.wfile.getvalue().decode("utf-8")
        parsed = json.loads(raw_output) if raw_output else {}
        return status_codes[-1], parsed

    # 1. GET /health
    code, res = call_handler("GET", "/health")
    assert code == 200
    assert res["status"] == "ready"

    # 2. GET /v1/slots
    code, res = call_handler("GET", "/v1/slots")
    assert code == 200
    assert res["count"] == 0

    # 3. GET /v1/models
    code, res = call_handler("GET", "/v1/models")
    assert code == 200
    assert len(res["catalog"]) >= 4

    # 4. GET /v1/license
    code, res = call_handler("GET", "/v1/license")
    assert code == 200
    assert res["tier"] == "COMMUNITY"

    # 5. POST /v1/license/activate
    comm_token = LicenseManager.generate_token(licensee="Test Enterprise", seat_count=20)
    code, res = call_handler("POST", "/v1/license/activate", {"license_key": comm_token})
    assert code == 200
    assert res["license"]["tier"] == "COMMERCIAL"
    assert mock_daemon.license.tier == "COMMERCIAL"


def test_model_catalog_entries():
    catalog = ModelManager.list_catalog()
    assert len(catalog) >= 4
    model_ids = [m["id"] for m in catalog]
    assert "qwen2.5-1.5b" in model_ids
    assert "llama-3.2-1b" in model_ids
    assert "gemma-2b-q4" in model_ids


def test_gguf_magic_header_verification(tmp_path):
    # Valid GGUF file starts with b'GGUF'
    valid_file = tmp_path / "model.gguf"
    valid_file.write_bytes(b"GGUF\x03\x00\x00\x00" + b"\x00" * 100)
    assert ModelManager.verify_gguf_header(str(valid_file)) is True

    # Invalid header
    bad_file = tmp_path / "bad.gguf"
    bad_file.write_bytes(b"NOTGGUF" + b"\x00" * 100)
    assert ModelManager.verify_gguf_header(str(bad_file)) is False
