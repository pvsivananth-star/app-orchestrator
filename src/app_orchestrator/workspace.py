"""Workspace management for .ox2 folder."""

import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class Workspace:
    """Manages the .ox2 workspace folder and artifacts."""

    def __init__(self, repo_path: Path):
        self.repo_path = Path(
            repo_path
        ).resolve()

        self.ox2_path = (
                self.repo_path / ".ox2"
        )

        self._ensure_workspace()

    def _ensure_workspace(self) -> None:
        """Create .ox2 folder and .gitignore entry if needed."""

        self.ox2_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        gitignore = (
                self.repo_path / ".gitignore"
        )

        if gitignore.exists():
            content = gitignore.read_text()

            if ".ox2/" not in content:
                with open(
                        gitignore,
                        "a",
                ) as f:
                    f.write(
                        "\n# App Orchestrator workspace\n"
                        ".ox2/\n"
                    )

                logger.info(
                    "Added .ox2/ to %s",
                    gitignore,
                )

        else:
            gitignore.write_text(
                ".ox2/\n"
            )

            logger.info(
                "Created %s with .ox2/ ignored",
                gitignore,
            )

        logger.info(
            "Workspace ready: repo=%s",
            self.repo_path,
        )

        logger.info(
            "Workspace artifacts: %s",
            self.ox2_path,
        )

    def read(
            self,
            filename: str,
    ) -> Optional[str]:
        """Read content of an artifact file."""

        filepath = (
                self.ox2_path / filename
        )

        logger.info(
            ".ox2 READ: %s",
            filepath,
        )

        if not filepath.exists():
            logger.warning(
                ".ox2 READ MISS: %s does not exist",
                filepath,
            )
            return None

        content = filepath.read_text()

        logger.info(
            ".ox2 READ OK: %s (%d bytes)",
            filepath,
            len(
                content.encode(
                    "utf-8"
                )
            ),
        )

        return content

    def write(
            self,
            filename: str,
            content: str,
    ) -> None:
        """Write content to an artifact file."""

        filepath = (
                self.ox2_path / filename
        )

        filepath.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        logger.info(
            ".ox2 WRITE: %s",
            filepath,
        )

        filepath.write_text(
            content
        )

        logger.info(
            ".ox2 WRITE OK: %s (%d bytes)",
            filepath,
            len(
                content.encode(
                    "utf-8"
                )
            ),
        )

    def delete(
            self,
            filename: str,
    ) -> None:
        """Delete an artifact file."""

        filepath = (
                self.ox2_path / filename
        )

        logger.info(
            ".ox2 DELETE: %s",
            filepath,
        )

        if filepath.exists():
            filepath.unlink()

            logger.info(
                ".ox2 DELETE OK: %s",
                filepath,
            )

    def list_files(self) -> List[str]:
        """List all artifact files."""

        if not self.ox2_path.exists():
            logger.warning(
                ".ox2 LIST: workspace does not exist: %s",
                self.ox2_path,
            )
            return []

        files = [
            f.name
            for f in self.ox2_path.iterdir()
            if f.is_file()
        ]

        logger.info(
            ".ox2 LIST: %d artifact file(s)",
            len(files),
        )

        logger.debug(
            ".ox2 FILES: %s",
            files,
        )

        return files

    def read_json(
            self,
            filename: str,
    ) -> Optional[Dict[str, Any]]:
        """Read a JSON artifact."""

        logger.info(
            ".ox2 READ JSON: %s",
            filename,
        )

        content = self.read(
            filename
        )

        if content is None:
            return None

        return json.loads(content)

    def write_json(
            self,
            filename: str,
            data: Dict[str, Any],
    ) -> None:
        """Write a JSON artifact."""

        logger.info(
            ".ox2 WRITE JSON: %s",
            filename,
        )

        self.write(
            filename,
            json.dumps(
                data,
                indent=2,
            ),
        )

    def clear(self) -> None:
        """Delete all artifacts."""

        logger.info(
            ".ox2 CLEAR: %s",
            self.ox2_path,
        )

        if self.ox2_path.exists():
            shutil.rmtree(
                self.ox2_path
            )

        self._ensure_workspace()

        logger.info(
            ".ox2 CLEAR COMPLETE: %s",
            self.ox2_path,
        )