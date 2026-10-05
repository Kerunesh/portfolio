"""Processed project IDs in a JSON file, written atomically so a crash never corrupts it."""

import json
import os
from typing import Iterable, Optional

MAX_IDS = 5000


class SeenStorage:
    def __init__(self, path: Optional[str]):
        """path=None keeps IDs in memory only (dry run)."""
        self._path = path
        self._ids = []
        self._index = set()
        self.initialized = False
        self._load()

    def _load(self) -> None:
        if self._path is None or not os.path.exists(self._path):
            return
        with open(self._path, "r", encoding="utf-8") as f:
            state = json.load(f)
        self._ids = [int(i) for i in state.get("seen", [])]
        self._index = set(self._ids)
        self.initialized = True

    def is_seen(self, project_id: int) -> bool:
        return project_id in self._index

    def mark(self, project_ids: Iterable[int]) -> None:
        for project_id in project_ids:
            if project_id not in self._index:
                self._ids.append(project_id)
                self._index.add(project_id)
        if len(self._ids) > MAX_IDS:
            self._ids = self._ids[-MAX_IDS:]
            self._index = set(self._ids)
        self.initialized = True
        self._save()

    def _save(self) -> None:
        if self._path is None:
            return
        directory = os.path.dirname(self._path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        tmp_path = self._path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"seen": self._ids}, f)
        os.replace(tmp_path, self._path)
