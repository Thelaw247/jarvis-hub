"""The Jarvis browser on Laptop B: a persistent signed-in profile, Claude's browser tools on Playwright, and the
browse worker. JARVIS_DESIGN_TOOLS.md §6."""
from .service import BrowseResult, BrowserService

__all__ = ["BrowserService", "BrowseResult"]
