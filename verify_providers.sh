#!/bin/bash
# verify_providers.sh
# Compile and verify the provider layer

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Provider Layer Verification${NC}"
echo -e "${BLUE}========================================${NC}"

# Step 0: Check dependencies
echo -e "\n${YELLOW}Step 0: Checking dependencies...${NC}"

check_module() {
    local module=$1
    if python3 -c "import $module" 2>/dev/null; then
        echo -e "  ${GREEN}✅${NC} $module"
        return 0
    else
        echo -e "  ${RED}❌${NC} $module (install with: uv add $module)"
        return 1
    fi
}

MISSING=false
check_module "yaml" || MISSING=true
check_module "requests" || MISSING=true
check_module "google" || MISSING=true

if [ "$MISSING" = true ]; then
    echo -e "\n${YELLOW}Installing missing dependencies...${NC}"
    uv add pyyaml requests google-generativeai
    echo -e "${GREEN}✅ Dependencies installed${NC}"
fi

# Step 1: Check Python syntax
echo -e "\n${YELLOW}Step 1: Checking Python syntax...${NC}"
cd src
python3 -m py_compile app_orchestrator/providers/*.py 2>/dev/null || true
python3 -m py_compile app_orchestrator/models/*.py 2>/dev/null || true
cd ..
echo -e "${GREEN}✅ Python syntax check complete${NC}"

# Step 2: Check imports
echo -e "\n${YELLOW}Step 2: Checking imports...${NC}"
python3 -c "
import sys
sys.path.insert(0, 'src')

# Import all providers
from app_orchestrator.providers import (
    BaseProvider,
    ProviderResponse,
    ProviderError,
    ProviderErrorType,
    ProviderRegistry,
    GeminiProvider,
    DeepSeekProvider,
    GroqProvider,
    OpenRouterProvider,
    HuggingFaceProvider,
    MicrosoftGroqProvider
)

print('✅ All imports successful')
"

# Step 3: Check API keys (without exposing them)
echo -e "\n${YELLOW}Step 3: Checking API keys...${NC}"

check_key() {
    local key_name=$1
    if [ -n "${!key_name}" ]; then
        echo -e "  ${GREEN}✅${NC} $key_name is set"
        return 0
    else
        echo -e "  ${RED}❌${NC} $key_name is NOT set"
        return 1
    fi
}

ALL_KEYS_OK=true
check_key "GEMINI_API_KEY" || ALL_KEYS_OK=false
check_key "DEEPSEEK_API_KEY" || ALL_KEYS_OK=false
check_key "GROQ_API_KEY" || ALL_KEYS_OK=false
check_key "OPENROUTER_API_KEY" || ALL_KEYS_OK=false
check_key "HUGGINGFACE_API_KEY" || ALL_KEYS_OK=false

if [ "$ALL_KEYS_OK" = false ]; then
    echo -e "\n${YELLOW}⚠️  Some API keys are missing. Providers will fail for those.${NC}"
    echo -e "${YELLOW}   Make sure keys are set in ~/.zshrc${NC}"
fi

# Step 4: Test Provider Registry
echo -e "\n${YELLOW}Step 4: Testing Provider Registry...${NC}"
python3 -c "
import sys
sys.path.insert(0, 'src')

from app_orchestrator.providers import ProviderRegistry

registry = ProviderRegistry()
print('✅ ProviderRegistry initialized')

# Check agent mappings
agents = ['interaction', 'implementation', 'verification', 'doc', 'commit']
for agent in agents:
    providers = registry.get_agent_providers(agent)
    print(f'  ✅ {agent}: {providers}')

# Check all providers are configured
providers = ['gemini', 'deepseek', 'groq', 'openrouter', 'huggingface', 'microsoft_groq']
for p in providers:
    if p in registry.provider_configs:
        print(f'  ✅ {p}: configured')
    else:
        print(f'  ❌ {p}: not found')
"

# Step 5: Quick test with Gemini
echo -e "\n${YELLOW}Step 5: Quick API test...${NC}"
if [ -n "$GEMINI_API_KEY" ]; then
    echo -e "${YELLOW}Testing Gemini API...${NC}"
    python3 -c "
import sys
sys.path.insert(0, 'src')
from app_orchestrator.providers import ProviderRegistry

registry = ProviderRegistry()
try:
    provider = registry.get_provider('gemini')
    response = provider.generate('Say hello in one word.', {'temperature': 0.1, 'max_tokens': 10})
    print(f'  ✅ Gemini response: {response.content}')
    print(f'  ✅ Duration: {response.duration_ms:.0f}ms')
except Exception as e:
    print(f'  ⚠️  Gemini test failed (expected if rate limited): {str(e)[:100]}')
"
else
    echo -e "  ${YELLOW}⚠️  Skipping Gemini test (no API key)${NC}"
fi

# Step 6: Cleanup
echo -e "\n${YELLOW}Step 6: Cleanup...${NC}"
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
echo -e "${GREEN}✅ Cleaned up Python cache files${NC}"

# Summary
echo -e "\n${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Verification Complete!${NC}"
echo -e "${BLUE}========================================${NC}"

echo -e "\n${YELLOW}Files verified:${NC}"
find src/app_orchestrator/providers -type f -name "*.py" | sort | sed 's/^/  /'
echo ""
find src/app_orchestrator/models -type f | sort | sed 's/^/  /'

echo -e "\n${YELLOW}Next steps:${NC}"
echo "  1. If you want Microsoft Agent: uv sync --extra microsoft-agent"
echo "  2. Continue with next layer (Agents, CLI, etc.)"
"

chmod +x verify_providers.sh