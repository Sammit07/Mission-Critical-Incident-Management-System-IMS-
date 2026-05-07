"""
Throughput metrics service.
Prints signals/sec to the console every METRICS_INTERVAL_SECONDS (default 5 s).
Uses a monotonic-time sliding window so the rate is always over the last 5 s.
"""
from __future__ import annotations

import asyncio
import time
from collections import deque


class MetricsService:
    def __init__(self) -> None:
        self._timestamps: deque[float] = deque()
        self._total_signals: int = 0
        self._total_work_items: int = 0
        self._lock = asyncio.Lock()
        self._running = False

    async def record_signal(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps.append(now)
            self._total_signals += 1
            # Evict entries older than 5 s to keep the deque lean
            cutoff = now - 5.0
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

    async def record_work_item(self) -> None:
        async with self._lock:
            self._total_work_items += 1

    def get_throughput(self) -> float:
        if len(self._timestamps) < 2:
            return float(len(self._timestamps))
        window = self._timestamps[-1] - self._timestamps[0]
        return len(self._timestamps) / max(window, 0.001)

    def get_stats(self) -> dict:
        return {
            "signals_per_sec": round(self.get_throughput(), 2),
            "total_signals": self._total_signals,
            "total_work_items": self._total_work_items,
        }

    async def start_periodic_reporting(self, interval: int = 5) -> None:
        self._running = True
        while self._running:
            await asyncio.sleep(interval)
            s = self.get_stats()
            print(
                f"[METRICS] {s['signals_per_sec']:.2f} signals/sec | "
                f"total signals: {s['total_signals']:,} | "
                f"work items: {s['total_work_items']:,}",
                flush=True,
            )

    def stop(self) -> None:
        self._running = False


metrics_service = MetricsService()
