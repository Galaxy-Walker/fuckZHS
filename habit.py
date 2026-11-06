#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Persistent state for the daily habit-score sessions.

The server awards at most one "regular study" per calendar day, so the state is
keyed by account + course + date.  A session is only counted after the target
number of seconds has been reached on that day.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime


def _now():
    return datetime.now().astimezone()


def _today():
    return _now().strftime("%Y-%m-%d")


def fmt_seconds(seconds) -> str:
    seconds = max(0, int(seconds or 0))
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


class HabitState:
    VERSION = 1

    def __init__(self, path: str, account: str, course_id: str,
                 target_sessions: int = 5, minutes: int = 25):
        self.path = os.path.realpath(path)
        self.account = str(account or "default")
        self.course_id = str(course_id)
        self.target_sessions = max(1, int(target_sessions))
        self.minutes = max(1, int(minutes))
        self.target_seconds = self.minutes * 60
        self.data = self._load()

    # ------------------------------------------------------------------ data
    def _empty(self):
        return {"version": self.VERSION, "accounts": {}}

    def _load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = self._empty()
        if not isinstance(data, dict):
            data = self._empty()
        data.setdefault("version", self.VERSION)
        accounts = data.setdefault("accounts", {})
        if not isinstance(accounts, dict):
            accounts = {}
            data["accounts"] = accounts
        acc = accounts.setdefault(self.account, {})
        if not isinstance(acc, dict):
            acc = {}
            accounts[self.account] = acc
        courses = acc.setdefault("courses", {})
        if not isinstance(courses, dict):
            courses = {}
            acc["courses"] = courses
        course = courses.setdefault(self.course_id, {})
        if not isinstance(course, dict):
            course = {}
            courses[self.course_id] = course
        course.setdefault("days", {})
        if not isinstance(course["days"], dict):
            course["days"] = {}
        course["target_sessions"] = self.target_sessions
        course["minutes"] = self.minutes
        return data

    @property
    def course(self) -> dict:
        return self.data["accounts"][self.account]["courses"][self.course_id]

    @property
    def days(self) -> dict:
        return self.course["days"]

    def _today_record(self, create: bool = True):
        record = self.days.get(_today())
        if record is None and create:
            record = {"seconds": 0, "completed": False}
            self.days[_today()] = record
        return record

    # ----------------------------------------------------------------- state
    def today_seconds(self) -> int:
        record = self._today_record(create=False)
        return int(record.get("seconds", 0)) if record else 0

    def today_completed(self) -> bool:
        record = self._today_record(create=False)
        return bool(record and record.get("completed"))

    def completed_sessions(self) -> int:
        return sum(1 for record in self.days.values() if record.get("completed"))

    def remaining_seconds(self) -> int:
        return max(0, self.target_seconds - self.today_seconds())

    def can_start(self):
        """Return (allowed, reason). reason is 'done', 'today' or ''."""
        if self.completed_sessions() >= self.target_sessions:
            return False, "done"
        if self.today_completed():
            return False, "today"
        return True, ""

    def add_seconds(self, seconds: int, save: bool = True):
        seconds = int(seconds or 0)
        if seconds <= 0:
            return
        record = self._today_record()
        record["seconds"] = int(record.get("seconds", 0)) + seconds
        record["updated_at"] = _now().isoformat(timespec="seconds")
        if record["seconds"] >= self.target_seconds:
            record["completed"] = True
        if save:
            self.save()

    def mark_today_complete(self) -> bool:
        record = self._today_record()
        if record.get("completed"):
            return False
        record["completed"] = True
        record["seconds"] = max(int(record.get("seconds", 0)), self.target_seconds)
        record["updated_at"] = _now().isoformat(timespec="seconds")
        self.save()
        return True

    def reset(self):
        self.course["days"] = {}
        self.save()

    # ------------------------------------------------------------------- io
    def save(self):
        self.data["version"] = self.VERSION
        directory = os.path.dirname(self.path) or "."
        os.makedirs(directory, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=".habit_state.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            try:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            except OSError:
                pass

    # --------------------------------------------------------------- display
    def status_text(self) -> str:
        lines = [
            f"课程: {self.course_id}",
            f"进度: {self.completed_sessions()}/{self.target_sessions} 次",
        ]
        done = [day for day, record in sorted(self.days.items()) if record.get("completed")]
        if done:
            lines.append("已完成: " + ", ".join(done))
        record = self._today_record(create=False)
        if record and record.get("completed"):
            lines.append(f"今天 ({_today()}): 已完成")
        else:
            lines.append(
                f"今天 ({_today()}): {fmt_seconds(self.today_seconds())} / "
                f"{fmt_seconds(self.target_seconds)}"
            )
        return "\n".join(lines)

    @staticmethod
    def summary_all(path: str, target_sessions: int = 5, minutes: int = 25) -> str:
        path = os.path.realpath(path)
        if not os.path.isfile(path):
            return f"暂无习惯分记录（{path} 不存在）"
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            return f"读取习惯分记录失败: {exc}"
        accounts = data.get("accounts") or {}
        if not accounts:
            return "暂无习惯分记录"
        lines = [f"习惯分记录: {path}"]
        for account, acc in accounts.items():
            courses = (acc or {}).get("courses") or {}
            for course_id, course in courses.items():
                days = (course or {}).get("days") or {}
                target = int((course or {}).get("target_sessions") or target_sessions)
                completed = sum(1 for record in days.values() if record.get("completed"))
                lines.append("")
                lines.append(f"账号 {account} / 课程 {course_id}")
                lines.append(f"  进度: {completed}/{target} 次")
                done = [day for day, record in sorted(days.items()) if record.get("completed")]
                if done:
                    lines.append("  已完成: " + ", ".join(done))
                record = days.get(_today())
                if record and record.get("completed"):
                    lines.append(f"  今天 ({_today()}): 已完成")
                elif record:
                    lines.append(
                        f"  今天 ({_today()}): {fmt_seconds(record.get('seconds', 0))} / "
                        f"{fmt_seconds(int((course or {}).get('minutes') or minutes) * 60)}"
                    )
        return "\n".join(lines)
