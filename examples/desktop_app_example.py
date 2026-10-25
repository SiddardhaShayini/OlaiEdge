#!/usr/bin/env python3
"""
FastAgent Edge: Example Desktop Application Integration (Code Editor / Note App)
Demonstrates multi-tab slot caching, memory budget inspection, and grammar-constrained JSON.
"""
import time
from fast_agent import (
    FastAgent,
    MemoryBudgetManager,
    SlotCacheManager,
    GrammarEngine,
    LicenseManager,
)


def main():
    print("=" * 65)
    print("[*] FastAgent Edge Engine: Desktop App Integration Showcase")
    print("=" * 65)

    # 1. License Check (Community or Commercial)
    license_token = LicenseManager.generate_token(
        licensee="DevCraft Studio IDE",
        seat_count=25,
        max_slots=16,
    )
    license = LicenseManager.verify_license(license_token)
    print(f"\n[License] Active Tier: {license.tier} ({license.licensee})")
    print(f"          Max Active Tab Slots: {license.max_concurrent_slots}")

    # 2. Memory Budget Manager (Protects 8GB consumer PCs from OOM)
    memory_mgr = MemoryBudgetManager(budget_mb=2048)
    snapshot = memory_mgr.get_system_snapshot()
    print(f"\n[Memory] Total System RAM: {snapshot['total_system_ram_mb']} MB")
    print(f"         Available RAM:    {snapshot['available_system_ram_mb']} MB")
    print(f"         Engine Budget:    {snapshot['engine_budget_mb']} MB")
    print(f"         RAM Utilization:  {snapshot['budget_utilization_percent']}%")

    # 3. Multi-Tab Slot Caching (Simulating 3 Open Tabs in a Desktop Code Editor)
    slot_mgr = SlotCacheManager(max_active_slots=license.max_concurrent_slots)
    slot_mgr.set_pinned_system_prompt("System: You are an autonomous code refactoring edge engine.")

    # Tab 1: utils.py
    print("\n[Tab 1] Switching to 'src/utils.py' tab...")
    tab1 = slot_mgr.get_or_create_slot("tab-utils-py")
    tab1.add_user_turn("Refactor format_currency() to support EUR and GBP.")
    tab1.append_agent_turn("Refactored format_currency with currency symbol mapping.")

    # Tab 2: parser.py
    print("[Tab 2] Switching to 'src/parser.py' tab...")
    tab2 = slot_mgr.get_or_create_slot("tab-parser-py")
    tab2.add_user_turn("Add AST error handling for unclosed brackets.")
    tab2.append_agent_turn("Added SyntaxError catcher for bracket mismatch.")

    # Tab 3: main.py
    print("[Tab 3] Switching to 'src/main.py' tab...")
    tab3 = slot_mgr.get_or_create_slot("tab-main-py")
    tab3.add_user_turn("Wire up CLI argument flags.")
    tab3.append_agent_turn("Integrated argparse with --budget and --slots flags.")

    print(f"\n[Slot Manager] Active Document Tabs in Memory: {slot_mgr.active_slot_count()}")
    for slot_info in slot_mgr.list_slots():
        print(f"  * {slot_info['session_id']}: {slot_info['turns_in_memory']} turns cached")

    # 4. Grammar-Constrained JSON Extraction (Code Editor Patch)
    print("\n[Grammar Engine] Enforcing strict AST Code Patch schema...")
    patch_schema = GrammarEngine.get_desktop_schema("code_editor_patch")
    gbnf_grammar = GrammarEngine.json_schema_to_gbnf(patch_schema)
    print(f"Generated GBNF Grammar ({len(gbnf_grammar)} chars) to guarantee 100% syntactically valid edits.")

    sample_llm_json = """{
        "file_path": "src/utils.py",
        "action": "replace",
        "start_line": 15,
        "end_line": 20,
        "replacement_code": "def format_currency(val, symbol='$'): return f'{symbol}{val:.2f}'",
        "commit_message": "Add EUR/GBP currency formatting"
    }"""
    valid, parsed_patch, err = GrammarEngine.validate_and_parse(sample_llm_json, patch_schema)
    assert valid is True
    print(f"[AST Patch Applied] File: {parsed_patch['file_path']} | Action: {parsed_patch['action']}")
    print(f"                    Line: {parsed_patch['start_line']} | Message: {parsed_patch['commit_message']}")

    print("\n" + "=" * 65)
    print("[+] FastAgent Edge Engine is ready for drop-in desktop app deployment!")
    print("=" * 65)


if __name__ == "__main__":
    main()
