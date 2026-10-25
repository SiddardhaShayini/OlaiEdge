# fast_agent/memory_manager.py
"""
Memory Budget and Crash Prevention System for FastAgent Edge.
Ensures local LLM execution never exceeds user-configured RAM limits on consumer machines.
"""
import os
import threading
import time
from typing import Any, Callable, Dict, Optional
import psutil


class MemoryPressureWarning(Exception):
    """Raised when memory consumption approaches critical limits."""
    pass


class MemoryBudgetManager:
    """
    Monitors host RAM and manages memory budgets for edge LLM execution.
    Calculates safe context window lengths, KV quantization, and watchdog triggers
    to guarantee desktop apps do not crash with Out-Of-Memory (OOM) errors.
    """

    def __init__(
        self,
        budget_mb: Optional[int] = None,
        safety_headroom_mb: int = 512,
        check_interval_sec: float = 1.0,
        critical_threshold_percent: float = 88.0,
        on_pressure_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        """
        Args:
            budget_mb: Maximum memory (in MB) the engine process is permitted to consume.
                       If None, auto-calculated based on available system RAM.
            safety_headroom_mb: Safety buffer reserved for OS and host desktop application.
            check_interval_sec: Watchdog poll interval in seconds.
            critical_threshold_percent: System RAM usage percentage that triggers memory circuit breaker.
            on_pressure_callback: Function called when high memory pressure is detected.
        """
        self.safety_headroom_mb = safety_headroom_mb
        self.check_interval_sec = check_interval_sec
        self.critical_threshold_percent = critical_threshold_percent
        self.on_pressure_callback = on_pressure_callback

        # Determine budget
        sys_mem = psutil.virtual_memory()
        total_ram_mb = int(sys_mem.total / (1024 * 1024))
        available_ram_mb = int(sys_mem.available / (1024 * 1024))

        if budget_mb is not None:
            self.budget_mb = budget_mb
        else:
            # Auto-calculate: On 8GB or smaller machines, allocate at most 50% of available RAM or 2048 MB
            if total_ram_mb <= 8192:
                self.budget_mb = min(2048, max(512, available_ram_mb - safety_headroom_mb))
            else:
                self.budget_mb = min(4096, max(1024, int(available_ram_mb * 0.6)))

        self.current_process = psutil.Process(os.getpid())
        self.target_process: Optional[psutil.Process] = None
        self._watchdog_thread: Optional[threading.Thread] = None
        self._stop_watchdog = threading.Event()
        self.is_throttled = False
        self.last_metrics: Dict[str, Any] = {}

    def attach_engine_process(self, pid: int):
        """Attach watchdog to the spawned llama-server child process."""
        try:
            self.target_process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            self.target_process = None

    def get_system_snapshot(self) -> Dict[str, Any]:
        """Returns real-time RAM and process metrics."""
        sys_mem = psutil.virtual_memory()
        engine_rss_mb = 0.0
        if self.target_process:
            try:
                engine_rss_mb = self.target_process.memory_info().rss / (1024 * 1024)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                engine_rss_mb = 0.0

        host_rss_mb = self.current_process.memory_info().rss / (1024 * 1024)

        metrics = {
            "total_system_ram_mb": round(sys_mem.total / (1024 * 1024), 1),
            "available_system_ram_mb": round(sys_mem.available / (1024 * 1024), 1),
            "system_ram_used_percent": sys_mem.percent,
            "engine_budget_mb": self.budget_mb,
            "engine_rss_mb": round(engine_rss_mb, 1),
            "host_rss_mb": round(host_rss_mb, 1),
            "total_agent_rss_mb": round(engine_rss_mb + host_rss_mb, 1),
            "budget_utilization_percent": round(
                ((engine_rss_mb + host_rss_mb) / self.budget_mb) * 100, 1
            ) if self.budget_mb > 0 else 0.0,
            "is_throttled": self.is_throttled,
        }
        self.last_metrics = metrics
        return metrics

    def compute_optimal_engine_params(
        self,
        model_size_mb: float,
        desired_context: int = 2048,
    ) -> Dict[str, Any]:
        """
        Dynamically calculates optimal llama-server arguments based on the memory budget.
        Recommends context size, KV quantization (q8_0 vs q4_0), and batch sizes.
        """
        # Estimated KV cache memory consumption per 1024 tokens:
        # FP16 KV cache: ~250MB per 1024 tokens for 2B-3B model
        # Q8_0 KV cache: ~125MB per 1024 tokens
        # Q4_0 KV cache: ~65MB per 1024 tokens
        remaining_budget_mb = self.budget_mb - model_size_mb
        if remaining_budget_mb <= 0:
            # Very tight budget: enforce minimum context and aggressive quantization
            return {
                "context_size": min(1024, desired_context),
                "ctk": "q4_0",
                "ctv": "q4_0",
                "batch_size": 128,
                "n_threads": max(1, (os.cpu_count() or 4) // 2),
                "recommendation": "CRITICAL_MEMORY_BUDGET",
            }

        if remaining_budget_mb < 300:
            context_size = min(1024, desired_context)
            ctk = "q4_0"
            ctv = "q4_0"
            batch_size = 256
        elif remaining_budget_mb < 600:
            context_size = min(2048, desired_context)
            ctk = "q8_0"
            ctv = "q8_0"
            batch_size = 256
        else:
            context_size = desired_context
            ctk = "q8_0"
            ctv = "q8_0"
            batch_size = 512

        return {
            "context_size": context_size,
            "ctk": ctk,
            "ctv": ctv,
            "batch_size": batch_size,
            "n_threads": max(1, (os.cpu_count() or 4) - 1),
            "recommendation": "OPTIMAL",
        }

    def start_watchdog(self):
        """Starts background watchdog thread."""
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            return
        self._stop_watchdog.clear()
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop,
            name="FastAgent-MemoryWatchdog",
            daemon=True,
        )
        self._watchdog_thread.start()

    def stop_watchdog(self):
        """Stops watchdog thread cleanly."""
        self._stop_watchdog.set()
        if self._watchdog_thread:
            self._watchdog_thread.join(timeout=2.0)
            self._watchdog_thread = None

    def _watchdog_loop(self):
        """Continuous watchdog checking RAM pressure."""
        while not self._stop_watchdog.is_set():
            try:
                metrics = self.get_system_snapshot()
                total_used_mb = metrics["total_agent_rss_mb"]
                sys_percent = metrics["system_ram_used_percent"]

                # Check if process exceeds allocated budget or system memory exceeds critical threshold
                if total_used_mb > self.budget_mb or sys_percent >= self.critical_threshold_percent:
                    if not self.is_throttled:
                        self.is_throttled = True
                        if self.on_pressure_callback:
                            self.on_pressure_callback(metrics)
                else:
                    # De-escalate when memory safely drops below 80% of budget
                    if self.is_throttled and total_used_mb < (self.budget_mb * 0.8):
                        self.is_throttled = False
            except Exception:
                pass
            time.sleep(self.check_interval_sec)

    def check_headroom_or_raise(self):
        """Circuit breaker check: raises MemoryPressureWarning if memory is unsafe."""
        metrics = self.get_system_snapshot()
        if metrics["system_ram_used_percent"] > 95.0:
            raise MemoryPressureWarning(
                f"Emergency memory circuit breaker: System RAM is at {metrics['system_ram_used_percent']}%. "
                "Execution aborted to prevent desktop OS crash."
            )
        if metrics["budget_utilization_percent"] > 110.0:
            raise MemoryPressureWarning(
                f"Memory budget exceeded: Engine RSS is {metrics['engine_rss_mb']}MB "
                f"exceeding budget of {self.budget_mb}MB."
            )
