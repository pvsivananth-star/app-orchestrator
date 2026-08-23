#!/bin/bash
# setup_cache_and_providers.sh
# Updates mapping.yaml to use high-limit providers and adds response caching

set -e

echo "=== Updating provider priorities and adding caching ==="

# 1. Update mapping.yaml – prioritize Groq and DeepSeek, keep Gemini for specific agents
cat > src/app_orchestrator/models/mapping.yaml << 'EOF'
providers:
  gemini:
    name: gemini
    model: gemini-3.6-flash
    env_vars: [GEMINI_API_KEY]
    timeout: 30
    max_retries: 5
    retry_delay: 1.0
  deepseek:
    name: deepseek
    model: deepseek-chat
    env_vars: [DEEPSEEK_API_KEY]
    timeout: 30
    max_retries: 5
    retry_delay: 1.0
  groq:
    name: groq
    model: mixtral-8x7b-32768
    env_vars: [GROQ_API_KEY]
    timeout: 30
    max_retries: 5
    retry_delay: 1.0
  openrouter:
    name: openrouter
    model: openai/gpt-3.5-turbo
    env_vars: [OPENROUTER_API_KEY]
    timeout: 30
    max_retries: 5
    retry_delay: 1.0
  huggingface:
    name: huggingface
    model: meta-llama/Llama-2-70b-chat-hf
    env_vars: [HUGGINGFACE_API_KEY]
    timeout: 60
    max_retries: 5
    retry_delay: 2.0
  microsoft_groq:
    name: microsoft_groq
    model: mixtral-8x7b-32768
    env_vars: [GROQ_API_KEY]
    timeout: 30
    max_retries: 5
    retry_delay: 1.0

agents:
  # Heavy reasoning – DeepSeek first
  interaction:
    - deepseek
    - groq
    - openrouter
    - microsoft_groq
    - FAIL
  
  requirement_enhancer:
    - deepseek
    - groq
    - openrouter
    - microsoft_groq
    - FAIL
  
  business_analyst:
    - deepseek
    - groq
    - openrouter
    - microsoft_groq
    - FAIL
  
  # Code generation – DeepSeek first
  implementation:
    - deepseek
    - groq
    - openrouter
    - microsoft_groq
    - FAIL
  
  # Fast checks – Groq first
  verification:
    - groq
    - deepseek
    - openrouter
    - microsoft_groq
    - FAIL
  
  security:
    - groq
    - deepseek
    - openrouter
    - microsoft_groq
    - FAIL
  
  lint:
    - groq
    - deepseek
    - openrouter
    - microsoft_groq
    - FAIL
  
  test:
    - groq
    - deepseek
    - openrouter
    - microsoft_groq
    - FAIL
  
  # Repository analysis – Gemini (used once per run)
  repo_analyst:
    - gemini
    - deepseek
    - groq
    - microsoft_groq
    - FAIL
  
  # Documentation – Gemini (used once per run)
  doc:
    - gemini
    - deepseek
    - groq
    - microsoft_groq
    - FAIL
  
  # Commit – OpenRouter first (specialized)
  commit:
    - openrouter
    - deepseek
    - groq
    - microsoft_groq
    - FAIL
  
  dependency:
    - huggingface
    - deepseek
    - groq
    - microsoft_groq
    - FAIL
EOF

echo "✅ Updated mapping.yaml with prioritized providers"

# 2. Add caching to base.py
cat > src/app_orchestrator/providers/base.py << 'EOF'
from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, Any, Optional, List
import time
import logging
from enum import Enum
import hashlib
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# Cache directory – inside .ox2
CACHE_DIR = Path(".ox2/cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Environment flag to disable cache (set to "1" to disable)
DISABLE_CACHE = bool(int(os.getenv("APP_ORCHESTRATOR_DISABLE_CACHE", "0")))

class ProviderErrorType(Enum):
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    INVALID_REQUEST = "invalid_request"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"

@dataclass
class ProviderResponse:
    content: str
    provider: str
    model: str
    usage: Optional[Dict[str, int]] = None
    duration_ms: float = 0.0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

@dataclass
class ProviderError(Exception):
    error_type: ProviderErrorType
    message: str
    provider: str
    retryable: bool = True
    details: Optional[Dict[str, Any]] = None
    
    def __str__(self):
        return f"[{self.provider}] {self.error_type.value}: {self.message}"

class BaseProvider(ABC):
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_name = config.get("name", self.__class__.__name__)
        self.timeout = config.get("timeout", 30)
        self.max_retries = config.get("max_retries", 5)
        self.retry_delay = config.get("retry_delay", 1.0)
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        pass
    
    @abstractmethod
    def _generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        pass
    
    def _get_cache_key(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate a unique cache key from the prompt and context."""
        # Include provider name to avoid cross-provider collisions
        data = {
            "provider": self.provider_name,
            "prompt": prompt,
            "context": {k: v for k, v in context.items() if k != "temperature"}  # exclude non-deterministic params
        }
        # Sort keys for consistency
        key_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _read_cache(self, cache_key: str) -> Optional[ProviderResponse]:
        """Read a cached response if available."""
        if DISABLE_CACHE:
            return None
        cache_file = CACHE_DIR / f"{cache_key}.json"
        if not cache_file.exists():
            return None
        try:
            data = json.loads(cache_file.read_text())
            # Reconstruct the response object
            response = ProviderResponse(
                content=data["content"],
                provider=data["provider"],
                model=data["model"],
                usage=data.get("usage"),
                duration_ms=data.get("duration_ms", 0.0),
                timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else None
            )
            logger.debug(f"Cache hit for {self.provider_name}")
            return response
        except Exception as e:
            logger.warning(f"Cache read failed: {e}")
            return None
    
    def _write_cache(self, cache_key: str, response: ProviderResponse):
        """Write a response to cache."""
        if DISABLE_CACHE:
            return
        try:
            cache_file = CACHE_DIR / f"{cache_key}.json"
            data = asdict(response)
            # Convert datetime to ISO string
            if data.get("timestamp"):
                data["timestamp"] = data["timestamp"].isoformat()
            cache_file.write_text(json.dumps(data, indent=2))
            logger.debug(f"Cached response for {self.provider_name}")
        except Exception as e:
            logger.warning(f"Cache write failed: {e}")
    
    def generate(self, prompt: str, context: Dict[str, Any]) -> ProviderResponse:
        """Public generate method with retry logic and caching."""
        # Check cache first
        cache_key = self._get_cache_key(prompt, context)
        cached = self._read_cache(cache_key)
        if cached:
            return cached
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = self._generate(prompt, context)
                response.duration_ms = (time.time() - start_time) * 1000
                response.provider = self.provider_name
                
                logger.info(f"Provider {self.provider_name} success")
                
                # Write to cache
                self._write_cache(cache_key, response)
                
                return response
            except ProviderError as e:
                last_error = e
                if not e.retryable:
                    raise
                wait_time = self.retry_delay * (2 ** attempt)
                logger.warning(f"Provider {self.provider_name} attempt {attempt+1} failed, retry in {wait_time:.1f}s")
                time.sleep(wait_time)
                continue
            except Exception as e:
                raise ProviderError(
                    error_type=ProviderErrorType.UNKNOWN,
                    message=f"Unexpected error: {str(e)}",
                    provider=self.provider_name,
                    retryable=False
                )
        raise ProviderError(
            error_type=ProviderErrorType.UNKNOWN,
            message=f"All {self.max_retries} retries exhausted",
            provider=self.provider_name,
            retryable=False
        )
    
    def _parse_error_response(self, status_code: int, response_data: Dict) -> ProviderError:
        error_type = ProviderErrorType.UNKNOWN
        message = "Unknown error"
        retryable = False
        if status_code == 429:
            error_type = ProviderErrorType.RATE_LIMIT
            message = "Rate limit exceeded"
            retryable = True
        elif status_code in [500, 502, 503, 504]:
            error_type = ProviderErrorType.SERVER_ERROR
            message = "Server error"
            retryable = True
        elif status_code == 401:
            error_type = ProviderErrorType.AUTHENTICATION
            message = "Invalid API key"
            retryable = False
        elif status_code == 408:
            error_type = ProviderErrorType.TIMEOUT
            message = "Timeout"
            retryable = True
        return ProviderError(
            error_type=error_type,
            message=message,
            provider=self.provider_name,
            retryable=retryable,
            details={"status_code": status_code, "response": response_data}
        )
EOF

echo "✅ Added caching to base.py"

# 3. Add environment variable for disabling cache (optional)
cat >> .env.example << 'EOF'
# Set to "1" to disable response caching (useful for testing)
APP_ORCHESTRATOR_DISABLE_CACHE=0
EOF

echo "✅ Added cache control to .env.example"

# 4. Create cache directory
mkdir -p .ox2/cache
echo "✅ Created .ox2/cache directory"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Provider priorities updated:"
echo "  - Groq and DeepSeek now primary for most agents"
echo "  - Gemini reserved for repo_analyst and doc"
echo ""
echo "Caching enabled:"
echo "  - Cache directory: .ox2/cache"
echo "  - Responses are cached based on prompt + context"
echo "  - To disable cache: export APP_ORCHESTRATOR_DISABLE_CACHE=1"
echo ""
echo "You can now develop with fewer API calls."
EOF

chmod +x setup_cache_and_providers.sh
./setup_cache_and_providers.sh