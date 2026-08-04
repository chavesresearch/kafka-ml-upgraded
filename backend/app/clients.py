"""Dependency provider for the shared HTTP client.

Created once at app startup (see ``app/main.py``'s lifespan) and handed out
per-request here, instead of the original Django code's pattern of opening a
brand new ``requests`` connection on every single call.
"""

import httpx
from litestar.datastructures import State


async def provide_http_client(state: State) -> httpx.AsyncClient:
    return state.http_client
