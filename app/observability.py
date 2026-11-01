from __future__ import annotations

import os


def configure_profiling(application_name: str) -> None:
    if os.getenv("PYROSCOPE_ENABLED", "false").lower() != "true":
        return

    server_address = os.getenv("PYROSCOPE_SERVER_ADDRESS")
    if not server_address:
        raise RuntimeError("PYROSCOPE_SERVER_ADDRESS is required when profiling is enabled")

    import pyroscope

    pyroscope.configure(
        application_name=os.getenv("PYROSCOPE_APPLICATION_NAME", application_name),
        server_address=server_address,
        tags={
            "environment": os.getenv(
                "DEPLOYMENT_ENVIRONMENT",
                os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "unknown")),
            )
        },
    )
