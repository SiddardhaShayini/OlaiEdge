# olaiedge/__init__.py
"""
OlaiEdge: Hardware-Adaptive Edge Agent Engine for Desktop Apps.
(Successor to FastAgent)
"""
from .core import (
    OlaiEngine,
    OlaiAgent,
    FastAgent,
    FastAgentEngine,
    AdaptiveComputeController,
    find_llama_server,
    find_free_port,
    is_port_in_use,
    safe_parse_args,
    REACT_GRAMMAR,
)
from .daemon import OlaiDaemon, FastAgentDaemon, get_runtime_metadata_path
from .grammar_engine import GrammarEngine, DESKTOP_SCHEMAS
from .license_manager import OlaiLicense, FastAgentLicense, LicenseManager, LicenseTier
from .memory_manager import MemoryBudgetManager, MemoryPressureWarning
from .model_catalog import ModelManager, EDGE_MODEL_CATALOG
from .slot_manager import SessionSlot, SlotCacheManager

__version__ = "1.0.0"

__all__ = [
    "OlaiEngine",
    "OlaiAgent",
    "OlaiDaemon",
    "OlaiLicense",
    "FastAgent",
    "FastAgentEngine",
    "FastAgentDaemon",
    "FastAgentLicense",
    "AdaptiveComputeController",
    "MemoryBudgetManager",
    "MemoryPressureWarning",
    "SlotCacheManager",
    "SessionSlot",
    "GrammarEngine",
    "DESKTOP_SCHEMAS",
    "ModelManager",
    "EDGE_MODEL_CATALOG",
    "LicenseManager",
    "LicenseTier",
    "find_llama_server",
    "find_free_port",
    "is_port_in_use",
    "safe_parse_args",
    "REACT_GRAMMAR",
    "get_runtime_metadata_path",
]
