"""Workspace management for .ox2 folder."""

import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class Workspace:
    """Manages the .ox2 workspace folder and artifacts."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()
        self.ox2_path = self.repo_path / ".ox2"
        self._ensure_workspace()
    
    def _ensure_workspace(self):
        """Create .ox2 folder and .gitignore entry if needed."""
        self.ox2_path.mkdir(parents=True, exist_ok=True)
        gitignore = self.repo_path / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            if ".ox2/" not in content:
                with open(gitignore, "a") as f:
                    f.write("\n# App Orchestrator workspace\n.ox2/\n")
        else:
            gitignore.write_text(".ox2/\n")
    
    def read(self, filename: str) -> Optional[str]:
        """Read content of an artifact file."""
        filepath = self.ox2_path / filename
        if not filepath.exists():
            return None
        return filepath.read_text()
    
    def write(self, filename: str, content: str):
        """Write content to an artifact file."""
        filepath = self.ox2_path / filename
        filepath.write_text(content)
        logger.debug(f"Wrote {filename}")
    
    def delete(self, filename: str):
        """Delete an artifact file."""
        filepath = self.ox2_path / filename
        if filepath.exists():
            filepath.unlink()
            logger.debug(f"Deleted {filename}")
    
    def list_files(self) -> List[str]:
        """List all artifact files."""
        return [f.name for f in self.ox2_path.iterdir() if f.is_file()]
    
    def read_json(self, filename: str) -> Optional[Dict[str, Any]]:
        """Read a JSON artifact."""
        content = self.read(filename)
        if content is None:
            return None
        return json.loads(content)
    
    def write_json(self, filename: str, data: Dict[str, Any]):
        """Write a JSON artifact."""
        self.write(filename, json.dumps(data, indent=2))
    
    def clear(self):
        """Delete all artifacts."""
        shutil.rmtree(self.ox2_path)
        self._ensure_workspace()
