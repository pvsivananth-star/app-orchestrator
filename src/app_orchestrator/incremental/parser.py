"""Response parsers for different model outputs."""

import re
from typing import List, Tuple

from ..constants import FILE_PATTERN, CODE_BLOCK_PATTERN


class ResponseParser:
    """Parse code files from model responses."""

    @staticmethod
    def parse_files(response: str) -> List[Tuple[str, str]]:
        """Parse files from response with multiple fallback patterns."""
        if not response or not response.strip():
            return []

        result = []

        # PATTERN 1: Standard format with FILE marker and code block
        matches1 = re.findall(FILE_PATTERN, response, re.DOTALL)
        if matches1:
            for filepath, content in matches1:
                result.append((filepath.strip(), content.strip()))
            return result

        # PATTERN 2: Code block with language specifier but no FILE marker
        matches2 = re.findall(CODE_BLOCK_PATTERN, response, re.DOTALL)
        if matches2:
            for i, content in enumerate(matches2):
                content = content.strip()
                if content:
                    if i == 0:
                        filepath = "src/main.py"
                    elif i == 1:
                        filepath = "src/test_main.py"
                    else:
                        filepath = f"src/file_{i+1}.py"
                    result.append((filepath, content))
            return result

        # PATTERN 3: Plain code with no markers (if it looks like Python)
        if "def " in response or "class " in response or "import " in response:
            lines = response.split('\n')
            code_lines = []
            in_code = False
            for line in lines:
                if line.strip().startswith('def ') or line.strip().startswith('class ') or line.strip().startswith('import '):
                    in_code = True
                    code_lines.append(line)
                elif in_code and (line.startswith('    ') or line.startswith('\t') or not line.strip()):
                    code_lines.append(line)
                elif in_code and line.strip() and not line.startswith('    ') and not line.startswith('\t'):
                    in_code = False
                    if code_lines:
                        content = '\n'.join(code_lines).strip()
                        if content:
                            result.append(("src/main.py", content))
                            code_lines = []
            if code_lines:
                content = '\n'.join(code_lines).strip()
                if content:
                    result.append(("src/main.py", content))

        return result
