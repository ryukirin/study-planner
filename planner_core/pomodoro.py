"""番茄钟状态机：空闲 → 专注 → 休息 → 空闲。时钟可注入，便于测试。"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

MODE_NAMES = {"idle": "空闲", "focus": "专注", "short_break": "短休息", "long_break": "长休息"}


@dataclass
class PomodoroEvent:
    kind: str  # focus_done / break_done
    minutes: int
    task: dict[str, Any] | None
    next_mode: str


class Pomodoro:
    def __init__(self, settings: Callable[[], dict[str, int]], clock: Callable[[], float] = time.time) -> None:
        self._settings = settings
        self._clock = clock
        self._lock = threading.RLock()
        self.mode = "idle"
        self.task: dict[str, Any] | None = None
        self.ends_at: float | None = None
        self.duration = 0
        self.paused_remaining: float | None = None
        self.completed = 0  # 本轮已完成的专注次数，用于决定长休息

    def _start(self, mode: str, minutes: int) -> None:
        self.mode = mode
        self.duration = minutes
        self.ends_at = self._clock() + minutes * 60
        self.paused_remaining = None

    def start_focus(self, task: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.task = task
            self._start("focus", self._settings()["focus"])

    def pause(self) -> None:
        with self._lock:
            if self.mode != "idle" and self.paused_remaining is None and self.ends_at is not None:
                self.paused_remaining = max(self.ends_at - self._clock(), 0)

    def resume(self) -> None:
        with self._lock:
            if self.paused_remaining is not None:
                self.ends_at = self._clock() + self.paused_remaining
                self.paused_remaining = None

    def stop(self) -> None:
        """放弃当前这一轮，不记录专注。"""
        with self._lock:
            self.mode = "idle"
            self.ends_at = None
            self.paused_remaining = None
            self.task = None

    def skip_break(self) -> None:
        with self._lock:
            if self.mode in ("short_break", "long_break"):
                self.stop()

    def tick(self) -> list[PomodoroEvent]:
        """到时间时推进状态。专注结束自动进入休息，休息结束回到空闲。"""
        events: list[PomodoroEvent] = []
        with self._lock:
            if self.mode == "idle" or self.paused_remaining is not None or self.ends_at is None:
                return events
            if self._clock() < self.ends_at:
                return events
            settings = self._settings()
            if self.mode == "focus":
                self.completed += 1
                long_break = self.completed % settings["long_every"] == 0
                next_mode = "long_break" if long_break else "short_break"
                events.append(PomodoroEvent("focus_done", self.duration, self.task, next_mode))
                self._start(next_mode, settings["long_break" if long_break else "short_break"])
            else:
                events.append(PomodoroEvent("break_done", self.duration, self.task, "idle"))
                self.mode = "idle"
                self.ends_at = None
                self.task = None
        return events

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            remaining = None
            if self.paused_remaining is not None:
                remaining = self.paused_remaining
            elif self.ends_at is not None:
                remaining = max(self.ends_at - self._clock(), 0)
            return {
                "mode": self.mode, "mode_name": MODE_NAMES[self.mode], "task": self.task, "duration": self.duration,
                "ends_at_ms": int(self.ends_at * 1000) if self.ends_at and self.paused_remaining is None else None,
                "remaining_s": round(remaining) if remaining is not None else None,
                "paused": self.paused_remaining is not None, "completed": self.completed,
            }
