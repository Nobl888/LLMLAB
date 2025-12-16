#!/bin/bash
#
# predeploy.sh - Pre-deployment sanity check
# Run this before pushing to a deployment branch to catch packaging errors
# that would cause ModuleNotFoundError on Render.
#
# Usage: ./predeploy.sh
# Exit code: 0 = all checks pass, 1 = failures detected

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED=0

echo "================================================"
echo "  Pre-Deployment Sanity Checks"
echo "================================================"
echo ""

# Check 1: Critical files are tracked
echo "✓ Check 1: Critical files are tracked..."
CRITICAL_FILES=(
    "api_validation/startup.py"
    "api_validation/__init__.py"
    "api_validation/public/__init__.py"
    "api_validation/public/main.py"
    "api_validation/public/schemas.py"
    "api_validation/public/settings.py"
    "api_validation/public/routes/__init__.py"
    "api_validation/public/routes/health.py"
    "api_validation/public/routes/validate.py"
    "api_validation/public/routes/auth.py"
    "domain_kits/__init__.py"
)

MISSING_FILES=()
for file in "${CRITICAL_FILES[@]}"; do
    if ! git ls-files --error-unmatch "$file" > /dev/null 2>&1; then
        MISSING_FILES+=("$file")
    fi
done

if [ ${#MISSING_FILES[@]} -gt 0 ]; then
    echo -e "${RED}✗ FAIL: Critical files not tracked by git:${NC}"
    for file in "${MISSING_FILES[@]}"; do
        echo "  - $file"
    done
    FAILED=1
else
    echo -e "${GREEN}  All critical files are tracked${NC}"
fi
echo ""

# Check 2: No untracked files in critical directories
echo "✓ Check 2: No untracked files in critical directories..."
UNTRACKED=$(git status -u --porcelain | grep '^??' | grep -E '(api_validation/|domain_kits/)' || true)
if [ -n "$UNTRACKED" ]; then
    echo -e "${RED}✗ FAIL: Untracked files in deployment directories:${NC}"
    echo "$UNTRACKED" | while read -r line; do
        echo "  - ${line#?? }"
    done
    echo -e "${YELLOW}  Run: git add <file> or add to .gitignore${NC}"
    FAILED=1
else
    echo -e "${GREEN}  No untracked files in critical directories${NC}"
fi
echo ""

# Check 3: Detect short/ambiguous imports
echo "✓ Check 3: Detecting problematic short imports..."
# Note: domain_kits is at repo root so "from domain_kits..." is correct
# Flag both 'from X import' and 'import X' forms for relative modules
SHORT_IMPORTS=$( (git grep -nE '^from (middleware|schemas|settings|routes|startup)\b' -- 'api_validation/**/*.py' || true; \
                  git grep -nE '^import (middleware|schemas|settings|routes|startup)\b' -- 'api_validation/**/*.py' || true) 2>/dev/null | sort -u)

if [ -n "$SHORT_IMPORTS" ]; then
    echo -e "${RED}✗ FAIL: Short imports detected (will fail on Render):${NC}"
    echo "$SHORT_IMPORTS" | head -20
    if [ $(echo "$SHORT_IMPORTS" | wc -l) -gt 20 ]; then
        echo "  ... ($(echo "$SHORT_IMPORTS" | wc -l) total matches)"
    fi
    echo ""
    echo -e "${YELLOW}  Fix: Use package-qualified imports like:${NC}"
    echo "    from api_validation.public.schemas import ..."
    echo "    from api_validation.public.middleware import ..."
    FAILED=1
else
    echo -e "${GREEN}  No problematic short imports detected${NC}"
fi
echo ""

# Check 4: __pycache__ pollution check
echo "✓ Check 4: Checking for __pycache__ pollution..."
PYCACHE_FILES=$(git ls-files | grep '__pycache__' || true)
if [ -n "$PYCACHE_FILES" ]; then
    echo -e "${YELLOW}⚠ WARNING: __pycache__ files are tracked (should be in .gitignore):${NC}"
    echo "$PYCACHE_FILES" | head -10
    if [ $(echo "$PYCACHE_FILES" | wc -l) -gt 10 ]; then
        echo "  ... ($(echo "$PYCACHE_FILES" | wc -l) total files)"
    fi
    echo -e "${YELLOW}  Consider: git rm -r --cached **/__pycache__${NC}"
else
    echo -e "${GREEN}  No __pycache__ pollution${NC}"
fi
echo ""

# Check 5: Verify package structure
echo "✓ Check 5: Verifying package structure..."
MISSING_INIT=()
for dir in api_validation api_validation/public api_validation/public/routes api_validation/public/middleware domain_kits domain_kits/kpi_analytics; do
    if [ ! -f "$dir/__init__.py" ]; then
        MISSING_INIT+=("$dir/__init__.py")
    fi
done

if [ ${#MISSING_INIT[@]} -gt 0 ]; then
    echo -e "${RED}✗ FAIL: Missing __init__.py files:${NC}"
    for file in "${MISSING_INIT[@]}"; do
        echo "  - $file"
    done
    echo -e "${YELLOW}  Run: touch ${MISSING_INIT[@]}${NC}"
    FAILED=1
else
    echo -e "${GREEN}  Package structure is valid${NC}"
fi
echo ""

# Check 6: Middleware files tracked
echo "✓ Check 6: Verifying middleware files are tracked..."
MIDDLEWARE_FILES=(
    "api_validation/public/middleware/__init__.py"
    "api_validation/public/middleware/audit_logging.py"
    "api_validation/public/middleware/rate_limiting.py"
)

MISSING_MIDDLEWARE=()
for file in "${MIDDLEWARE_FILES[@]}"; do
    if ! git ls-files --error-unmatch "$file" > /dev/null 2>&1; then
        MISSING_MIDDLEWARE+=("$file")
    fi
done

if [ ${#MISSING_MIDDLEWARE[@]} -gt 0 ]; then
    echo -e "${RED}✗ FAIL: Middleware files not tracked:${NC}"
    for file in "${MISSING_MIDDLEWARE[@]}"; do
        echo "  - $file"
    done
    echo -e "${YELLOW}  Run: git add api_validation/public/middleware/${NC}"
    FAILED=1
else
    echo -e "${GREEN}  All middleware files are tracked${NC}"
fi
echo ""

# Check 7: Requirements.txt validation (Tweak A: validate at repo root)
echo "✓ Check 7: Validating requirements.txt..."
REQUIREMENTS_FILE="./requirements.txt"

if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo -e "${RED}✗ FAIL: requirements.txt not found at repo root${NC}"
    echo -e "${YELLOW}  Render build expects: pip install -r requirements.txt${NC}"
    FAILED=1
elif ! git ls-files --error-unmatch "$REQUIREMENTS_FILE" > /dev/null 2>&1; then
    echo -e "${RED}✗ FAIL: requirements.txt not tracked by git${NC}"
    echo -e "${YELLOW}  Run: git add requirements.txt${NC}"
    FAILED=1
else
    # Check for essential packages
    REQUIRED_PACKAGES=("fastapi" "uvicorn" "pydantic")
    MISSING_PACKAGES=()
    for pkg in "${REQUIRED_PACKAGES[@]}"; do
        if ! grep -qi "^$pkg" "$REQUIREMENTS_FILE"; then
            MISSING_PACKAGES+=("$pkg")
        fi
    done
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo -e "${YELLOW}⚠ WARNING: Essential packages not in requirements.txt:${NC}"
        for pkg in "${MISSING_PACKAGES[@]}"; do
            echo "  - $pkg"
        done
    else
        echo -e "${GREEN}  requirements.txt is valid${NC}"
    fi
fi
echo ""

# Check 8: Import consistency - verify imported local modules exist (Tweak B: FAIL on missing)
echo "✓ Check 8: Verifying imported local modules are tracked..."
IMPORT_ERRORS=()

# Find all Python files in deployment directories
PYTHON_FILES=$(git ls-files 'api_validation/**/*.py' 'domain_kits/**/*.py' 2>/dev/null || true)

while IFS= read -r pyfile; do
    [ -z "$pyfile" ] && continue
    
    # Extract both forms: 'from X import Y' and 'import X'
    FROM_IMPORTS=$(grep -E '^from (api_validation|domain_kits)\.' "$pyfile" 2>/dev/null || true)
    PLAIN_IMPORTS=$(grep -E '^import (api_validation|domain_kits)\b' "$pyfile" 2>/dev/null || true)
    
    # Process 'from X import Y' style
    while IFS= read -r import_line; do
        [ -z "$import_line" ] && continue
        
        # Extract module path: "from api_validation.public.schemas import X" -> "api_validation.public.schemas"
        MODULE_PATH=$(echo "$import_line" | sed -E 's/^from ([a-zA-Z0-9_.]+) import .*/\1/')
        
        # Convert to file path: api_validation.public.schemas -> api_validation/public/schemas.py or schemas/__init__.py
        DIR_PATH="${MODULE_PATH//.//}"
        FILE_PATH="${DIR_PATH}.py"
        
        # Check if it's a tracked file or directory
        if ! git ls-files --error-unmatch "$FILE_PATH" > /dev/null 2>&1; then
            # Not a file, check if it's a package directory
            if [ -d "$DIR_PATH" ]; then
                # Verify __init__.py exists and is tracked
                if ! git ls-files --error-unmatch "${DIR_PATH}/__init__.py" > /dev/null 2>&1; then
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but ${DIR_PATH}/__init__.py not tracked")
                fi
            else
                # Neither file nor directory exists/tracked
                if [ ! -f "$FILE_PATH" ] && [ ! -d "$DIR_PATH" ]; then
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but neither $FILE_PATH nor $DIR_PATH/ exists")
                else
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but it's not tracked in git")
                fi
            fi
        fi
    done <<< "$FROM_IMPORTS"
    
    # Process 'import X' or 'import X as Y' style
    while IFS= read -r import_line; do
        [ -z "$import_line" ] && continue
        
        # Extract module path: "import api_validation.public.schemas" or "import api_validation.public.schemas as s"
        # Strip 'as alias' and comments
        MODULE_PATH=$(echo "$import_line" | sed -E 's/^import ([a-zA-Z0-9_.]+).*/\1/' | sed 's/#.*//' | xargs)
        
        # Convert to file path
        DIR_PATH="${MODULE_PATH//.//}"
        FILE_PATH="${DIR_PATH}.py"
        
        # Check if it's a tracked file or directory
        if ! git ls-files --error-unmatch "$FILE_PATH" > /dev/null 2>&1; then
            if [ -d "$DIR_PATH" ]; then
                if ! git ls-files --error-unmatch "${DIR_PATH}/__init__.py" > /dev/null 2>&1; then
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but ${DIR_PATH}/__init__.py not tracked")
                fi
            else
                if [ ! -f "$FILE_PATH" ] && [ ! -d "$DIR_PATH" ]; then
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but neither $FILE_PATH nor $DIR_PATH/ exists")
                else
                    IMPORT_ERRORS+=("$pyfile: imports $MODULE_PATH but it's not tracked in git")
                fi
            fi
        fi
    done <<< "$PLAIN_IMPORTS"
done <<< "$PYTHON_FILES"

if [ ${#IMPORT_ERRORS[@]} -gt 0 ]; then
    echo -e "${RED}✗ FAIL: Imported modules not tracked or missing:${NC}"
    for error in "${IMPORT_ERRORS[@]}"; do
        echo "  - $error"
    done
    echo -e "${YELLOW}  This will cause ModuleNotFoundError on Render${NC}"
    echo -e "${YELLOW}  Run: git add <missing-files> or fix imports${NC}"
    FAILED=1
else
    echo -e "${GREEN}  All imported local modules are tracked${NC}"
fi
echo ""

# Summary
echo "================================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED${NC}"
    echo "  Safe to deploy!"
    echo "================================================"
    exit 0
else
    echo -e "${RED}✗ CHECKS FAILED${NC}"
    echo "  Fix issues above before deploying"
    echo "================================================"
    exit 1
fi
