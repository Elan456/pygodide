"""Automatic conversion of simple sync Pygame loops to async-friendly form."""

from pygodide.asyncify.analyze import diagnose_entrypoint
from pygodide.asyncify.config import resolve_auto_async
from pygodide.asyncify.models import AsyncifyDiagnostic, AsyncifyResult
from pygodide.asyncify.transform import asyncify_entrypoint
from pygodide.asyncify.warnings import format_smoke_async_warnings

__all__ = [
    "AsyncifyDiagnostic",
    "AsyncifyResult",
    "asyncify_entrypoint",
    "diagnose_entrypoint",
    "format_smoke_async_warnings",
    "resolve_auto_async",
]
