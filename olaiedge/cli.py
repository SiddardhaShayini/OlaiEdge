# olaiedge/cli.py
"""
OlaiEdge CLI: Management, Benchmarking, and Runtime Daemon.
Usage:
    olai serve [--model PATH] [--port PORT] [--memory-budget-mb MB] [--parent-pid PID]
    olai status
    olai models [list|download]
    olai license [verify|generate]
    olai eval
"""
import argparse
import json
import os
import sys
from typing import Optional
import requests

from .daemon import OlaiDaemon, get_runtime_metadata_path
from .grammar_engine import GrammarEngine
from .license_manager import LicenseManager, LicenseTier
from .memory_manager import MemoryBudgetManager
from .model_catalog import EDGE_MODEL_CATALOG, ModelManager


def cmd_serve(args):
    print("=" * 60)
    print("⚡ OlaiEdge: Headless Desktop Agent Runtime")
    print("=" * 60)
    daemon = OlaiDaemon(
        model_path=args.model,
        port=args.port,
        host=args.host,
        memory_budget_mb=args.memory_budget_mb,
        parent_pid=args.parent_pid,
        license_key=args.license_key,
    )
    print(f"[*] Engine Status: ONLINE")
    print(f"[*] Endpoint:      http://{daemon.host}:{daemon.port}")
    print(f"[*] Memory Budget: {daemon.memory_manager.budget_mb} MB")
    print(f"[*] License Tier:  {daemon.license.tier}")
    print(f"[*] Press Ctrl+C to terminate.")
    print("-" * 60)
    daemon.start(blocking=True)


def cmd_status(args):
    lockfile = get_runtime_metadata_path()
    if not lockfile.exists():
        print("[!] No active OlaiEdge daemon lockfile found.")
        print(f"    Expected at: {lockfile}")
        sys.exit(1)

    try:
        with open(lockfile, "r") as f:
            meta = json.load(f)
    except Exception as e:
        print(f"[!] Error reading lockfile: {e}")
        sys.exit(1)

    url = f"http://{meta.get('host', '127.0.0.1')}:{meta.get('port', 8085)}/v1/status"
    try:
        resp = requests.get(url, timeout=2.0)
        resp.raise_for_status()
        status_data = resp.json()

        print("\n=== OlaiEdge Runtime Status ===")
        print(f"Daemon PID:       {meta.get('pid')}")
        print(f"Endpoint:         http://{meta.get('host')}:{meta.get('port')}")
        print(f"Active Model:     {status_data.get('model_path')}")
        mem = status_data.get("memory", {})
        print(f"Engine RSS:       {mem.get('engine_rss_mb')} MB")
        print(f"Memory Budget:    {mem.get('engine_budget_mb')} MB ({mem.get('budget_utilization_percent')}% utilized)")
        print(f"System Available: {mem.get('available_system_ram_mb')} MB (Total: {mem.get('total_system_ram_mb')} MB)")
        slots = status_data.get("slots", {})
        print(f"Active Slots:     {slots.get('active_count')} / {slots.get('max_allowed')} allowed")
        lic = status_data.get("license", {})
        print(f"License:          {lic.get('tier')} ({lic.get('licensee')}) - Valid: {lic.get('is_valid')}")
        print("===============================\n")

    except Exception as e:
        print(f"[!] OlaiEdge daemon is registered in lockfile but not responding at {url}: {e}")
        sys.exit(1)


def cmd_models(args):
    action = args.action or "list"

    if action == "list":
        print("\n=== Curated OlaiEdge Models ===")
        for mid, meta in EDGE_MODEL_CATALOG.items():
            print(f"• ID:          {mid}")
            print(f"  Name:        {meta['name']}")
            print(f"  Size:        {meta['size_mb']} MB (Min RAM: {meta['min_ram_mb']} MB)")
            print(f"  Best For:    {meta['ideal_for']}\n")

        print("=== Local Models Detected ===")
        local = ModelManager.find_local_models()
        if not local:
            print("  (No local .gguf models found in search paths)")
        for m in local:
            valid_tag = "Valid GGUF" if m["is_valid_gguf"] else "INVALID"
            print(f"  - {m['filename']} ({m['size_mb']} MB) [{valid_tag}]")
            print(f"    Path: {m['path']}")
        print()

    elif action == "download":
        if not args.model_id:
            print("[!] Please specify a model ID to download. Example: olai models download qwen2.5-1.5b")
            sys.exit(1)
        print(f"[*] Initiating download for '{args.model_id}'...")
        path = ModelManager.download_model(args.model_id)
        print(f"[✓] Model downloaded successfully to: {path}")


def cmd_license(args):
    action = args.action or "verify"

    if action == "verify":
        token = args.token or os.environ.get("OLAI_LICENSE_KEY")
        lic = LicenseManager.verify_license(token)
        print("\n=== OlaiEdge License Verification ===")
        print(f"Tier:               {lic.tier}")
        print(f"Licensee:           {lic.licensee}")
        print(f"Seat Count:         {lic.seat_count}")
        print(f"Max Concurrent Slots: {lic.max_concurrent_slots}")
        print(f"Status:             {'VALID' if lic.is_valid else 'INVALID'}")
        print(f"Message:            {lic.message}")
        print("=====================================\n")

    elif action == "generate":
        licensee = args.licensee or "Enterprise Partner"
        tier = args.tier or LicenseTier.COMMERCIAL
        seats = args.seats or 10
        slots = args.slots or 16
        days = args.days or 365
        token = LicenseManager.generate_token(
            licensee=licensee,
            tier=tier,
            seat_count=seats,
            max_slots=slots,
            validity_days=days,
        )
        print("\n=== Generated Commercial Developer License ===")
        print(f"Licensee: {licensee}")
        print(f"Tier:     {tier}")
        print(f"Seats:    {seats}")
        print(f"Slots:    {slots}")
        print(f"Validity: {days} days")
        print("\nLicense Token:")
        print(f"{token}")
        print("==============================================\n")


def cmd_eval(args):
    print("\n=== OlaiEdge Hardware Diagnostic Evaluation ===")
    mgr = MemoryBudgetManager()
    sys_stats = mgr.get_system_snapshot()
    print(f"Total System RAM:     {sys_stats['total_system_ram_mb']} MB")
    print(f"Available System RAM: {sys_stats['available_system_ram_mb']} MB")
    print(f"Recommended Budget:   {sys_stats['engine_budget_mb']} MB")
    print(f"RAM Pressure:         {sys_stats['system_ram_used_percent']}%")

    local_models = ModelManager.find_local_models()
    print(f"Local Models Found:   {len(local_models)}")
    for m in local_models:
        print(f"  • {m['filename']} ({m['size_mb']} MB)")
    print("================================================\n")


def main():
    parser = argparse.ArgumentParser(
        prog="olai",
        description="OlaiEdge: Headless Edge Agent Engine for Desktop Apps",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")

    p_serve = subparsers.add_parser("serve", help="Run the headless edge daemon")
    p_serve.add_argument("--model", default=None, help="Path or ID of GGUF model")
    p_serve.add_argument("--port", type=int, default=8085, help="Port to serve on (default: 8085)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
    p_serve.add_argument("--memory-budget-mb", type=int, default=None, help="RAM budget ceiling in MB")
    p_serve.add_argument("--parent-pid", type=int, default=None, help="Parent desktop process PID to watch")
    p_serve.add_argument("--license-key", default=None, help="Commercial license key")

    subparsers.add_parser("status", help="Query status of running OlaiEdge daemon")

    p_models = subparsers.add_parser("models", help="Model catalog management")
    p_models.add_argument("action", choices=["list", "download"], nargs="?", default="list")
    p_models.add_argument("model_id", nargs="?", default=None, help="Model ID to download")

    p_lic = subparsers.add_parser("license", help="License verification and generator")
    p_lic.add_argument("action", choices=["verify", "generate"], nargs="?", default="verify")
    p_lic.add_argument("--token", default=None, help="License token to verify")
    p_lic.add_argument("--licensee", default=None, help="Licensee name")
    p_lic.add_argument("--tier", default=LicenseTier.COMMERCIAL, help="License tier")
    p_lic.add_argument("--seats", type=int, default=10, help="Number of developer seats")
    p_lic.add_argument("--slots", type=int, default=16, help="Concurrent tab slots allowed")
    p_lic.add_argument("--days", type=int, default=365, help="Validity period in days")

    subparsers.add_parser("eval", help="Hardware diagnostic evaluation")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "models":
        cmd_models(args)
    elif args.command == "license":
        cmd_license(args)
    elif args.command == "eval":
        cmd_eval(args)


if __name__ == "__main__":
    main()
