"""
Unit tests for OlaiEdge (Successor to FastAgent).
Verifies OlaiEngine, memory budgeting, slot caching, and offline licensing.
"""
import json
import pytest

import olaiedge
from olaiedge import (
    OlaiEngine,
    OlaiAgent,
    OlaiLicense,
    LicenseTier,
    LicenseManager,
    MemoryBudgetManager,
    SlotCacheManager,
    GrammarEngine,
    ModelManager,
    safe_parse_args,
)


def test_olaiedge_imports():
    assert olaiedge.__version__ == "1.0.0"
    assert OlaiEngine is not None
    assert OlaiAgent is OlaiEngine


def test_olaiedge_license_generation_and_offline_verification():
    token = LicenseManager.generate_token(
        licensee="DevDesk Inc",
        tier=LicenseTier.COMMERCIAL,
        seat_count=30,
        max_slots=16,
    )
    assert token.startswith("OLAI-COMM-")
    lic = LicenseManager.verify_license(token)
    assert lic.is_valid is True
    assert lic.licensee == "DevDesk Inc"
    assert lic.seat_count == 30
    assert lic.max_concurrent_slots == 16


def test_olaiedge_memory_budget_enforcement():
    mgr = MemoryBudgetManager(budget_mb=1024)
    params = mgr.compute_optimal_engine_params(model_size_mb=750, desired_context=2048)
    assert params["ctk"] == "q4_0"
    assert params["ctv"] == "q4_0"
    assert params["context_size"] <= 1024


def test_olaiedge_slot_cache_multi_tab():
    slot_mgr = SlotCacheManager(max_active_slots=3)
    slot_mgr.set_pinned_system_prompt("System: OlaiEdge Copilot")

    tab1 = slot_mgr.get_or_create_slot("editor-tab-1")
    tab1.add_user_turn("Refactor function foo()")
    tab1.append_agent_turn("Refactored foo().")

    tab2 = slot_mgr.get_or_create_slot("editor-tab-2")
    tab2.add_user_turn("Write unit test for bar()")
    tab2.append_agent_turn("Test created.")

    prompt1 = slot_mgr.build_slot_prompt("editor-tab-1")
    assert "Refactor function foo()" in prompt1
    assert "Write unit test for bar()" not in prompt1


def test_olaiedge_desktop_grammar():
    schema = GrammarEngine.get_desktop_schema("code_editor_patch")
    gbnf = GrammarEngine.json_schema_to_gbnf(schema)
    assert "root ::=" in gbnf
    assert "code_editor_patch" in olaiedge.DESKTOP_SCHEMAS
    assert len(gbnf) > 0
