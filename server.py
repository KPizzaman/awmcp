import json
from typing import Dict, Optional

import httpx
from fastmcp import FastMCP

# cache of search results so fetch can return full data
SEARCH_CACHE: Dict[str, dict] = {}

def create_server(
    base_url: str = "http://localhost:5600/api/0",
    name: Optional[str] = None,
    instructions: Optional[str] = None,
) -> FastMCP:
    """Create a FastMCP server exposing ActivityWatch search and fetch tools."""

    mcp = FastMCP(
        name=name or "ActivityWatch MCP",
        instructions=instructions or "Search and fetch ActivityWatch window events.",
    )

    @mcp.tool()
    async def search(query: str, limit: int = 5, cursor: Optional[str] = None):
        """Search window events by title using ActivityWatch."""
        offset = int(cursor) if cursor else 0
        matches: list[dict] = []
        try:
            async with httpx.AsyncClient(base_url=base_url) as client:
                resp = await client.get("/buckets")
                resp.raise_for_status()
                buckets = [
                    bid
                    for bid, data in resp.json().items()
                    if data.get("type") == "aw-watcher-window"
                ]
                for bucket_id in buckets:
                    ev_resp = await client.get(
                        f"/buckets/{bucket_id}/events", params={"limit": 500}
                    )
                    ev_resp.raise_for_status()
                    for ev in ev_resp.json():
                        title = ev.get("data", {}).get("title", "")
                        if query.lower() in title.lower():
                            result_id = f"{bucket_id}:{ev['timestamp']}"
                            SEARCH_CACHE[result_id] = {"bucket": bucket_id, "event": ev}
                            matches.append(
                                {
                                    "id": result_id,
                                    "title": title,
                                    "url": f"activitywatch://{bucket_id}/{ev['timestamp']}",
                                }
                            )
        except httpx.HTTPError as e:
            return {
                "content": [{"type": "text", "text": f"Search failed: {e}"}],
                "isError": True,
            }

        paginated = matches[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(matches) else None
        return {"results": paginated, "next_cursor": next_cursor}

    @mcp.tool()
    async def fetch(id: str):
        """Fetch full event JSON for a search result."""
        data = SEARCH_CACHE.get(id)
        if data is None:
            try:
                bucket, ts = id.split(":", 1)
            except ValueError:
                return {
                    "content": [{"type": "text", "text": "Invalid id"}],
                    "isError": True,
                }
            try:
                async with httpx.AsyncClient(base_url=base_url) as client:
                    resp = await client.get(
                        f"/buckets/{bucket}/events", params={"start": ts, "end": ts}
                    )
                    resp.raise_for_status()
                    events = resp.json()
                    if not events:
                        return {
                            "content": [
                                {"type": "text", "text": "Event not found"}
                            ],
                            "isError": True,
                        }
                    ev = events[0]
            except httpx.HTTPError as e:
                return {
                    "content": [{"type": "text", "text": f"Fetch failed: {e}"}],
                    "isError": True,
                }
        else:
            bucket = data["bucket"]
            ev = data["event"]

        return {
            "id": id,
            "title": ev.get("data", {}).get("title", ""),
            "url": f"activitywatch://{bucket}/{ev['timestamp']}",
            "content": [{"type": "text", "text": json.dumps(ev, indent=2)}],
        }

    return mcp


if __name__ == "__main__":
    server = create_server()
    server.run(transport="http", port=3000)
