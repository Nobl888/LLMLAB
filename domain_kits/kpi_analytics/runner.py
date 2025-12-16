"""
KPI Analytics Domain Kit - Runner

Safe execution of customer KPI functions with:
- Syntax validation (AST parse before execution)
- 30-second timeout (signal.SIGALRM on Linux/macOS)
- Fixture validation (required columns present)
- Error capture (runtime errors → structured dict)

v1 Contract:
- Required columns: Country, Profit, (order_year OR orderyear)
- Required function: def compute_kpi(df: pd.DataFrame) -> Any
- Expected: Deterministic, no side effects
"""

import importlib.util
import tempfile
import json
from pathlib import Path
from typing import Dict, Any
import pandas as pd
import time
import signal
import ast
import numpy as np


class TimeoutError(Exception):
    """Raised when code execution exceeds time limit."""
    pass


def _infer_output_type(result):
    """
    Map diverse output types to canonical string names.
    
    Handles numpy/pandas types consistently.
    """
    if isinstance(result, bool):
        return "unknown"  # bool not supported
    if isinstance(result, (int, np.integer)):
        return "int"
    if isinstance(result, (float, np.floating)):
        return "float"
    if isinstance(result, dict):
        return "dict"
    if isinstance(result, pd.DataFrame):
        return "DataFrame"
    if isinstance(result, pd.Series):
        return "Series"
    return type(result).__name__


class KPIRunner:
    """Execute KPI functions with isolation and safety constraints."""
    
    # v1 Configuration
    EXECUTION_TIMEOUT_SECONDS = 30
    ALLOWED_OUTPUT_TYPES = ('int', 'float', 'dict', 'DataFrame', 'Series')
    REQUIRED_FIXTURE_COLUMNS = {'Country', 'Profit'}  # Plus year (order_year OR orderyear)
    
    def __init__(self):
        """Initialize runner with safety defaults."""
        pass
    
    def execute(self, kpi_module_path: str, test_data_csv: str) -> Dict[str, Any]:
        """
        Load and run KPI function from module against test data.
        
        Args:
            kpi_module_path: Path to .py file with compute_kpi(df) function
            test_data_csv: Path to test data CSV (superstore_sales.csv)
        
        Returns:
            Dict with keys:
            - output: The result from compute_kpi()
            - output_type: Type name (int, float, dict, DataFrame, Series)
            - execution_time_ms: Wall-clock time in milliseconds
            - status: 'success' or 'error'
            - error: (if status='error') Human-readable error message
        
        Safety mechanisms in v1 (enforced):
            - Validates fixture has required columns
            - Enforces 30-second timeout via SIGALRM (Linux/macOS main thread only)
            - Captures and classifies all exceptions
        
        Not enforced in v1 (planned for v1.1):
            - File system write blocking → use subprocess isolation
            - Memory limit enforcement → use resource.setrlimit or cgroups
            - Windows timeout support → use threading-based timeout
        """
        
        # Step 1: Validate fixture exists and has required columns
        try:
            fixture_df = pd.read_csv(test_data_csv)
            
            # Check required base columns
            required_base = self.REQUIRED_FIXTURE_COLUMNS
            missing_base = required_base - set(fixture_df.columns)
            
            # Check year column (either order_year or orderyear)
            has_year = ("order_year" in fixture_df.columns) or ("orderyear" in fixture_df.columns)
            
            # Return error if missing base OR missing year
            if missing_base or not has_year:
                missing_display = list(missing_base) if missing_base else []
                if not has_year:
                    missing_display.append("order_year/orderyear")
                return {
                    "output": None,
                    "status": "error",
                    "error": f"Fixture missing required columns: {missing_display}"
                }
        except FileNotFoundError:
            return {
                "output": None,
                "status": "error",
                "error": f"Fixture file not found: {test_data_csv}"
            }
        except Exception as e:
            return {
                "output": None,
                "status": "error",
                "error": f"Failed to load fixture: {str(e)}"
            }
        
        # Step 2: Validate syntax (AST parse)
        syntax_valid = self.validate_syntax(kpi_module_path)
        if not syntax_valid:
            return {
                "output": None,
                "status": "error",
                "error": "KPI module has syntax errors. Check Python syntax."
            }
        
        # Step 3: Execute with timeout + isolation
        start_time = time.time()
        try:
            # Setup timeout handler (SIGALRM)
            signal.signal(signal.SIGALRM, self._timeout_handler)
            signal.alarm(self.EXECUTION_TIMEOUT_SECONDS)
            
            # Load module dynamically
            spec = importlib.util.spec_from_file_location("kpi_module", kpi_module_path)
            if spec is None or spec.loader is None:
                signal.alarm(0)
                return {
                    "output": None,
                    "status": "error",
                    "error": "Failed to load module spec"
                }
            
            module = importlib.util.module_from_spec(spec)
            
            try:
                # Execute module (run all module-level code)
                spec.loader.exec_module(module)
                
                # Call the required function
                if not hasattr(module, 'compute_kpi'):
                    signal.alarm(0)  # Cancel alarm
                    return {
                        "output": None,
                        "status": "error",
                        "error": "Module does not define compute_kpi(df) function"
                    }
                
                result = module.compute_kpi(fixture_df)
            finally:
                signal.alarm(0)  # Cancel alarm (critical!)
            
            elapsed = time.time() - start_time
            
            # Return success with inferred output type
            output_type = _infer_output_type(result)
            
            return {
                "output": result,
                "output_type": output_type,
                "execution_time_ms": elapsed * 1000,
                "status": "success"
            }
        
        except TimeoutError:
            elapsed = time.time() - start_time
            return {
                "output": None,
                "status": "error",
                "error": f"Execution exceeded {self.EXECUTION_TIMEOUT_SECONDS}s timeout",
                "execution_time_ms": elapsed * 1000
            }
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "output": None,
                "status": "error",
                "error": str(e),
                "execution_time_ms": elapsed * 1000
            }
    
    def validate_syntax(self, kpi_module_path: str) -> bool:
        """
        Check if Python file is syntactically valid (AST parse).
        
        Args:
            kpi_module_path: Path to .py file
        
        Returns:
            True if valid syntax, False otherwise
        """
        try:
            with open(kpi_module_path, 'r') as f:
                code = f.read()
            ast.parse(code)
            return True
        except (SyntaxError, FileNotFoundError, IsADirectoryError):
            return False
    
    def _timeout_handler(self, signum, frame):
        """Signal handler for SIGALRM (timeout)."""
        raise TimeoutError("Execution timeout")
