"""Generic parser for structured files returned by code-generation providers."""

from __future__ import annotations

import re
from pathlib import PurePosixPath
from typing import List, Tuple


class ResponseParser:
    """Parse explicit FILE blocks without assuming an application domain."""

    _FILE_PATTERN = re.compile(r"##\s*FILE:\s*([^\n]+?)\s*\n```[^\n]*\n(.*?)```", re.DOTALL)

    @classmethod
    def parse_files(cls, response: str) -> List[Tuple[str, str]]:
        if not response or not response.strip():
            return []
        result: List[Tuple[str, str]] = []
        for filepath, content in cls._FILE_PATTERN.findall(response):
            path = cls._clean_path(filepath)
            if path and content.strip():
                result.append((path, content.strip() + "\n"))
        return result

    @staticmethod
    def _clean_path(filepath: str) -> str:
        value = filepath.strip().strip("`'\"").replace("\\", "/")
        path = PurePosixPath(value)
        if not value or value.startswith("/") or ".." in path.parts:
            return ""
        return str(path)
