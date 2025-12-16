"""
Application settings for API validation service.
Externalizes config for portability across Render/on-prem/cloud.
"""
import os


class AppSettings:
    """Application settings with environment variable support."""
    
    def __init__(self):
        # Runner timeout and default kit values (used for docs/logs; validate keeps enforcing its own logic)
        self.execution_timeout_seconds: int = int(os.getenv("EXECUTION_TIMEOUT_SECONDS", "30"))
        self.default_fixture_path: str = os.getenv(
            "DEFAULT_FIXTURE_PATH", 
            "domain_kits/kpi_analytics/fixtures/superstore_sales.csv"
        )
        self.default_baseline_kpi_path: str = os.getenv(
            "DEFAULT_BASELINE_KPI_PATH",
            "domain_kits/kpi_analytics/fixtures/kpi_oracle_baseline.py"
        )


settings = AppSettings()
