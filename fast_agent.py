# fast_agent.py
"""
FastAgent: Embeddable Edge Agent Engine for Desktop Apps.
Root module re-exporting the complete Edge Agent Engine runtime.
"""
from fast_agent_pkg.fast_agent import (
    FastAgent,
    FastAgentEngine,
    AdaptiveComputeController,
    FastAgentDaemon,
    MemoryBudgetManager,
    MemoryPressureWarning,
    SlotCacheManager,
    SessionSlot,
    GrammarEngine,
    DESKTOP_SCHEMAS,
    ModelManager,
    EDGE_MODEL_CATALOG,
    FastAgentLicense,
    LicenseManager,
    LicenseTier,
    find_llama_server,
    find_free_port,
    is_port_in_use,
    safe_parse_args,
    REACT_GRAMMAR,
    get_runtime_metadata_path,
)

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
