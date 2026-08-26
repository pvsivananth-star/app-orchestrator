"""Response parsers for different model outputs."""

import re
from typing import List, Tuple


class ResponseParser:
    """Parse code files from model responses."""

    @staticmethod
    def parse_files(response: str) -> List[Tuple[str, str]]:
        """Parse files from response with multiple fallback patterns."""
        if not response or not response.strip():
            return []

        result = []

        # PATTERN 1: Standard format with FILE marker and code block
        pattern1 = r"##\s*FILE:\s*([^\n]+?)\s*\n```(?:[a-zA-Z]+)?\s*\n(.*?)```"
        matches1 = re.findall(pattern1, response, re.DOTALL)
        if matches1:
            for filepath, content in matches1:
                filepath = filepath.strip()
                content = content.strip()
                if filepath and content:
                    result.append((filepath, content))
            return result

        # PATTERN 2: ```language ... ``` with no FILE marker
        pattern2 = r"```(?:python|java|javascript|text|java|js|py)?\s*\n(.*?)```"
        matches2 = re.findall(pattern2, response, re.DOTALL)
        if matches2:
            for i, content in enumerate(matches2):
                content = content.strip()
                if content:
                    if "def " in content or "class " in content or "import " in content:
                        filename = "main.py" if i == 0 else f"module_{i+1}.py"
                    elif "public class" in content or "import java" in content:
                        filename = "App.java" if i == 0 else f"Module{i+1}.java"
                    elif "function " in content or "const " in content:
                        filename = "main.js" if i == 0 else f"module_{i+1}.js"
                    else:
                        filename = f"file_{i+1}.txt"
                    result.append((filename, content))
            return result

        # PATTERN 3: Code blocks with no language
        pattern3 = r"```\s*\n(.*?)```"
        matches3 = re.findall(pattern3, response, re.DOTALL)
        if matches3:
            for i, content in enumerate(matches3):
                content = content.strip()
                if content:
                    filename = f"file_{i+1}.txt"
                    result.append((filename, content))
            return result

        # PATTERN 4: Plain code with no markers
        if "def " in response or "class " in response or "public class" in response:
            if "public class" in response:
                filename = "App.java"
            elif "def " in response or "class " in response:
                filename = "main.py"
            else:
                filename = "output.txt"
            result.append((filename, response.strip()))
            return result

        return result
