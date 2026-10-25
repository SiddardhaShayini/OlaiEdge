# fast_agent/slot_manager.py
"""
Slot Cache & Multi-Tab Session Manager for FastAgent Edge.
Manages Longest Common Prefix (LCP) prompt caching across multiple desktop tabs/sessions
with LRU eviction and zero-overhead memory reuse.
"""
from collections import OrderedDict
import time
from typing import Any, Dict, List, Optional


class SessionSlot:
    """Represents an isolated conversation or document tab slot."""

    def __init__(self, session_id: str, max_history_turns: int = 6):
        self.session_id = session_id
        self.max_history_turns = max_history_turns
        self.conversation_history: List[str] = []
        self.created_at = time.time()
        self.last_accessed_at = time.time()
        self.total_tokens_generated = 0
        self.total_prompt_eval_ms = 0.0
        self.turn_count = 0
        self.metadata: Dict[str, Any] = {}

    def touch(self):
        self.last_accessed_at = time.time()

    def add_user_turn(self, user_text: str):
        self.touch()
        self.conversation_history.append(f"User: {user_text.strip()}\nAgent:")
        if len(self.conversation_history) > self.max_history_turns:
            self.conversation_history = self.conversation_history[-self.max_history_turns:]
        self.turn_count += 1

    def append_agent_turn(self, agent_text: str, prompt_eval_ms: float = 0.0):
        self.touch()
        if self.conversation_history:
            self.conversation_history[-1] += f" {agent_text.strip()}"
        self.total_prompt_eval_ms += prompt_eval_ms

    def clear(self):
        self.conversation_history.clear()
        self.turn_count = 0
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "turn_count": self.turn_count,
            "turns_in_memory": len(self.conversation_history),
            "created_at": self.created_at,
            "last_accessed_at": self.last_accessed_at,
            "total_prompt_eval_ms": round(self.total_prompt_eval_ms, 2),
            "metadata": self.metadata,
        }


class SlotCacheManager:
    """
    Orchestrates slot caching for multi-tab desktop applications.
    Shares the root system prompt prefix across all tabs while maintaining
    strict session isolation and LRU memory eviction.
    """

    def __init__(
        self,
        max_active_slots: int = 4,
        default_history_turns: int = 6,
    ):
        self.max_active_slots = max_active_slots
        self.default_history_turns = default_history_turns
        self._slots: OrderedDict[str, SessionSlot] = OrderedDict()
        self.pinned_system_prompt: str = ""
        self.evicted_slots_archive: Dict[str, List[str]] = {}

    def set_pinned_system_prompt(self, system_prompt: str):
        """Sets the root immutable prefix prompt shared across all active slots."""
        self.pinned_system_prompt = system_prompt.strip()

    def get_or_create_slot(
        self,
        session_id: str = "default",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SessionSlot:
        """
        Retrieves an existing slot or creates a new one, evicting the least recently
        used slot if max_active_slots is reached.
        """
        if session_id in self._slots:
            slot = self._slots[session_id]
            self._slots.move_to_end(session_id)
            slot.touch()
            if metadata:
                slot.metadata.update(metadata)
            return slot

        # Check if we need to evict an LRU slot
        if len(self._slots) >= self.max_active_slots:
            self._evict_lru_slot()

        # Check if slot exists in cold archive
        slot = SessionSlot(session_id, max_history_turns=self.default_history_turns)
        if session_id in self.evicted_slots_archive:
            slot.conversation_history = self.evicted_slots_archive.pop(session_id)
            slot.turn_count = len(slot.conversation_history)

        if metadata:
            slot.metadata = metadata

        self._slots[session_id] = slot
        return slot

    def _evict_lru_slot(self):
        """Evicts the oldest accessed slot from RAM to cold memory archive."""
        if not self._slots:
            return
        lru_id, lru_slot = self._slots.popitem(last=False)
        # Archive history for zero-loss reactivation later
        self.evicted_slots_archive[lru_id] = list(lru_slot.conversation_history)

    def build_slot_prompt(self, session_id: str, new_user_text: Optional[str] = None) -> str:
        """
        Constructs the full prompt: [Pinned Root System Prompt] + [Slot History] + [New Turn].
        Preserves the Longest Common Prefix (LCP) at the beginning for sub-millisecond cache hits.
        """
        slot = self.get_or_create_slot(session_id)
        if new_user_text:
            slot.add_user_turn(new_user_text)

        history_block = "\n".join(slot.conversation_history)
        if self.pinned_system_prompt:
            if history_block:
                return f"{self.pinned_system_prompt}\n\n{history_block}"
            return self.pinned_system_prompt
        return history_block

    def evict_slot(self, session_id: str) -> bool:
        """Explicitly evicts a tab/slot from memory (e.g. user closes document tab)."""
        if session_id in self._slots:
            del self._slots[session_id]
            return True
        if session_id in self.evicted_slots_archive:
            del self.evicted_slots_archive[session_id]
            return True
        return False

    def compact_all_slots(self, keep_last_n_turns: int = 2):
        """Emergency compaction: reduces conversation history in all slots during memory pressure."""
        for slot in self._slots.values():
            if len(slot.conversation_history) > keep_last_n_turns:
                slot.conversation_history = slot.conversation_history[-keep_last_n_turns:]
        self.evicted_slots_archive.clear()

    def list_slots(self) -> List[Dict[str, Any]]:
        """Returns diagnostic list of all active slots and their memory metrics."""
        return [slot.to_dict() for slot in self._slots.values()]

    def active_slot_count(self) -> int:
        return len(self._slots)
