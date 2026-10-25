# fast_agent/__init__.py
"""
FastAgent: Embeddable Edge Agent Engine for Desktop Apps.
Provides a zero-overhead local LLM runtime with memory budgets, slot caching,
and grammar-constrained structured outputs for Electron, Tauri, and Flutter apps.
"""
from .core import (
    FastAgent,
    FastAgentEngine,
    AdaptiveComputeController,
    find_llama_server,
    find_free_port,
    is_port_in_use,
    safe_parse_args,
    REACT_GRAMMAR,
)
from .daemon import FastAgentDaemon, get_runtime_metadata_path
from .grammar_engine import GrammarEngine, DESKTOP_SCHEMAS
from .license_manager import FastAgentLicense, LicenseManager, LicenseTier
from .memory_manager import MemoryBudgetManager, MemoryPressureWarning
from .model_catalog import ModelManager, EDGE_MODEL_CATALOG
from .slot_manager import SessionSlot, SlotCacheManager

__all__ = [
    "FastAgent",
    "FastAgentEngine",
    "AdaptiveComputeController",
    "FastAgentDaemon",
    "MemoryBudgetManager",
    "MemoryPressureWarning",
    "SlotCacheManager",
    "SessionSlot",
    "GrammarEngine",
    "DESKTOP_SCHEMAS",
    "ModelManager",
    "EDGE_MODEL_CATALOG",
    "FastAgentLicense",
    "LicenseManager",
    "LicenseTier",
    "find_llama_server",
    "find_free_port",
    "is_port_in_use",
    "safe_parse_args",
    "REACT_GRAMMAR",
    "get_runtime_metadata_path",
]
