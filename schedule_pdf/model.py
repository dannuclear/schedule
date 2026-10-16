"""Загрузка JSON и справочники расписания."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class ScheduleData:
    meta: dict
    slots: list[dict]
    classes: list[dict]
    teachers: list[dict]
    rooms: list[dict]
    subjects: list[dict]
    lessons: list[dict]

    classes_by_id: dict = field(default_factory=dict)
    teachers_by_id: dict = field(default_factory=dict)
    rooms_by_id: dict = field(default_factory=dict)
    subjects_by_id: dict = field(default_factory=dict)
    slots_by_n: dict = field(default_factory=dict)

    by_class: dict = field(default_factory=lambda: defaultdict(list))
    by_teacher: dict = field(default_factory=lambda: defaultdict(list))
    by_room: dict = field(default_factory=lambda: defaultdict(list))

    # --- индексы ---

    def build_indexes(self) -> None:
        self.classes_by_id = {c["id"]: c for c in self.classes}
        self.teachers_by_id = {t["id"]: t for t in self.teachers}
        self.rooms_by_id = {r["id"]: r for r in self.rooms}
        self.subjects_by_id = {s["id"]: s for s in self.subjects}
        self.slots_by_n = {s["n"]: s for s in self.slots}

        self.by_class = defaultdict(list)
        self.by_teacher = defaultdict(list)
        self.by_room = defaultdict(list)

        for les in self.lessons:
            key = (les["day"], les["slot"])
            for cid in les["classes"]:
                self.by_class[(cid, *key)].append(les)
            for p in les.get("parts", []):
                tid = p.get("teacherId")
                if tid:
                    self.by_teacher[(tid, *key)].append(les)
                rid = p.get("roomId")
                if rid:
                    self.by_room[(rid, *key)].append(les)

    # --- фильтры ---

    def filter_by_part(self, part: str) -> None:
        if part == "all":
            return
        if part == "beginners":
            keep_grade = lambda g: 1 <= g <= 4
        elif part == "basic":
            keep_grade = lambda g: g >= 5
        else:
            raise ValueError(f"Неизвестная часть: {part}")

        keep_ids = {c["id"] for c in self.classes if keep_grade(c["grade"])}
        self.classes = [c for c in self.classes if c["id"] in keep_ids]
        self.lessons = [l for l in self.lessons
                        if all(cid in keep_ids for cid in l["classes"])]
        self.build_indexes()

    def filter_by_day(self, day: int) -> None:
        if day <= 0:
            return
        self.lessons = [l for l in self.lessons if l["day"] == day]
        self.build_indexes()


def load_schedule(path: str) -> ScheduleData:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    data = ScheduleData(
        meta=raw["meta"],
        slots=raw["slots"],
        classes=raw["classes"],
        teachers=raw["teachers"],
        rooms=raw["rooms"],
        subjects=raw["subjects"],
        lessons=raw["lessons"],
    )
    data.build_indexes()
    return data