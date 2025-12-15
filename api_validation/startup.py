# startup.py
# Runs before FastAPI app starts
# Injects private scoring logic from environment or disk

import os
import sys
from pathlib import Path


def setup_private_modules():
    """
    Initialize private modules from environment or disk.
    
    In development: reads from local private/ folder
    In production: reads from environment variable or Render disk
    """
    
    environment = os.getenv("ENVIRONMENT", "development")
    
    # Find the api_validation directory
    current_dir = Path(__file__).parent
    if current_dir.name == "public":
        # Running from public/ folder
        api_validation_dir = current_dir.parent
    else:
        # Running from api_validation/ folder
        api_validation_dir = current_dir
    
    private_dir = api_validation_dir / "private"
    
    # Ensure private directory exists
    private_dir.mkdir(exist_ok=True)
    
    if environment == "production":
        # Production: Load from Render environment
        core_scoring_code = os.getenv("CORE_SCORING_CODE")
        
        if core_scoring_code:
            # Write the code to disk
            core_scoring_file = private_dir / "core_scoring.py"
            with open(core_scoring_file, "w") as f:
                f.write(core_scoring_code)
            print(f"[STARTUP] Loaded core_scoring.py from CORE_SCORING_CODE environment variable")
        else:
            print(f"[STARTUP] WARNING: CORE_SCORING_CODE not found in environment")
            # Fallback to mock implementation
            _create_mock_scoring(private_dir)
    else:
        # Development: Load from local disk
        core_scoring_file = private_dir / "core_scoring.py"
        if not core_scoring_file.exists():
            print(f"[STARTUP] Creating mock core_scoring.py for development")
            _create_mock_scoring(private_dir)
        else:
            print(f"[STARTUP] Using local core_scoring.py")


def _create_mock_scoring(private_dir: Path):
    """Create a mock scoring module for development/testing."""
    core_scoring_file = private_dir / "core_scoring.py"
    
    mock_code = '''# Mock scoring logic (for development/testing only)
def calculate_risk_vector(input_data: dict) -> dict:
    """
    Mock implementation for development.
    
    In production, this calls the real scoring algorithm
    which stays hidden in private/core_scoring.py.
    """
    return {
        "composite_score": 8.7,
        "confidence": 0.94,
        "intermediate_signals": {}
    }
'''
    
    with open(core_scoring_file, "w") as f:
        f.write(mock_code)
    print(f"[STARTUP] Created mock core_scoring.py at {core_scoring_file}")


if __name__ == "__main__":
    setup_private_modules()
    print("[STARTUP] Private modules initialized successfully")
