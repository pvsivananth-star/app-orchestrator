"""Combiner — stitches tiny chunks into complete files."""

import re
from pathlib import Path
from typing import List, Dict, Any


class Combiner:
    """Combine tiny generated chunks into complete files."""

    def __init__(self, repo_path: Path):
        self.repo_path = repo_path

    def combine_java(self, output_file: str = "CalculatorApp.java") -> str:
        """Combine Java chunks into a single file."""
        chunks = []

        # Find all Java code blocks in .ox2/chunks/
        chunk_dir = self.repo_path / ".ox2" / "chunks"
        if not chunk_dir.exists():
            return ""

        for chunk_file in sorted(chunk_dir.glob("*.java")):
            content = chunk_file.read_text()
            # Extract only the code (remove markdown if present)
            code = self._extract_code(content)
            if code:
                chunks.append(code)

        if not chunks:
            return ""

        # Combine with imports at top
        imports = self._extract_imports(chunks)
        body = self._extract_body(chunks)

        final = imports + "\n\n" + body
        return final

    def _extract_code(self, content: str) -> str:
        """Extract code from markdown blocks."""
        # Remove markdown code fences
        content = re.sub(r'```(?:java|text)?\s*\n', '', content)
        content = re.sub(r'```\s*\n', '', content)
        return content.strip()

    def _extract_imports(self, chunks: List[str]) -> str:
        """Extract and deduplicate imports."""
        imports = set()
        for chunk in chunks:
            for line in chunk.split('\n'):
                if line.strip().startswith('import '):
                    imports.add(line.strip())
        return '\n'.join(sorted(imports))

    def _extract_body(self, chunks: List[str]) -> str:
        """Extract the main class body from chunks."""
        body_parts = []
        for chunk in chunks:
            lines = chunk.split('\n')
            in_class = False
            for line in lines:
                if 'class ' in line and '{' in line:
                    in_class = True
                    # Add opening brace
                    body_parts.append('    // === Chunk ===')
                elif in_class:
                    # Skip the class declaration line
                    if not (line.strip().startswith('public class') or line.strip().startswith('class')):
                        body_parts.append(line)
        return '\n'.join(body_parts)

    def write_combined(self, output_file: str):
        """Write combined file to repository."""
        combined = self.combine_java(output_file)
        if combined:
            output_path = self.repo_path / output_file
            output_path.write_text(combined)
            print(f"✅ Combined: {output_file}")
            return True
        return False
