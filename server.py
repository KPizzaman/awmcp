import json
import json
import asyncio
from datetime import datetime
from typing import Dict, Optional

from aw_client.client import ActivityWatchClient

from fastmcp import FastMCP

# cache of search results so fetch can return full data
SEARCH_CACHE: Dict[str, dict] = {}


def create_server(
    aw_host: str = "localhost",
    aw_port: int = 5600,
    name: Optional[str] = None,
    instructions: Optional[str] = None,
    debug: bool = False,
) -> FastMCP:
    """Create a FastMCP server exposing ActivityWatch search and fetch tools."""

    mcp = FastMCP(
        name=name or "ActivityWatch MCP",
        instructions=instructions or "Search and fetch ActivityWatch window events.",
    )

    client = ActivityWatchClient("aw-mcp", host=aw_host, port=aw_port)


    @mcp.tool()
    async def search(query: str, limit: int = 5, cursor: Optional[str] = None):
        """Search window events by title using ActivityWatch."""
        offset = int(cursor) if cursor else 0
        matches: list[dict] = []
        try:
            buckets = await asyncio.to_thread(client.get_buckets)
            for bucket_id, data in buckets.items():
                if data.get("type") != "aw-watcher-window":
                    continue
                events = await asyncio.to_thread(client.get_events, bucket_id, 500)
                for ev in events:
                    title = ev.data.get("title", "")
                    if query.lower() in title.lower():
                        ts = ev.timestamp.isoformat()
                        result_id = f"{bucket_id}:{ts}"
                        SEARCH_CACHE[result_id] = {
                            "bucket": bucket_id,
                            "event": ev.to_json_dict(),
                        }
                        matches.append(
                            {
                                "id": result_id,
                                "title": title,
                                "url": f"activitywatch://{bucket_id}/{ts}",
                            }
                        )
        except Exception as e:

            return {
                "content": [{"type": "text", "text": f"Search failed: {e}"}],
                "isError": True,
            }

        paginated = matches[offset : offset + limit]
        next_cursor = str(offset + limit) if offset + limit < len(matches) else None
        result = {"results": paginated, "next_cursor": next_cursor}
        if debug:
            print(
                json.dumps(
                    {
                        "tool": "search",
                        "input": {"query": query, "limit": limit, "cursor": cursor},
                        "output": result,
                    },
                    indent=2,
                )
            )
        return result

    @mcp.tool()
    async def fetch(id: str):
        """Fetch full event JSON for a search result."""
        data = SEARCH_CACHE.get(id)
        if data is None:
            try:
                bucket, ts = id.split(":", 1)
                dt = datetime.fromisoformat(ts)
                events = await asyncio.to_thread(
                    client.get_events, bucket, 1, dt, dt
                )
                if not events:
                    return {
                        "content": [
                            {"type": "text", "text": "Event not found"}
                        ],
                        "isError": True,
                    }
                ev = events[0].to_json_dict()

            except ValueError:
                return {
                    "content": [{"type": "text", "text": "Invalid id"}],
                    "isError": True,
                }
            except Exception as e:

                return {
                    "content": [{"type": "text", "text": f"Fetch failed: {e}"}],
                    "isError": True,
                }
        else:
            bucket = data["bucket"]
            ev = data["event"]

        result = {

            "id": id,
            "title": ev.get("data", {}).get("title", ""),
            "url": f"activitywatch://{bucket}/{ev['timestamp']}",
            "content": [{"type": "text", "text": json.dumps(ev, indent=2)}],
        }
        if debug:
            print(
                json.dumps(
                    {
                        "tool": "fetch",
                        "input": {"id": id},
                        "output": result,
                    },
                    indent=2,
                )
            )
        return result


    return mcp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--aw-host", default="localhost")
    parser.add_argument("--aw-port", type=int, default=5600)
    parser.add_argument("--port", type=int, default=3000, help="MCP server port")
    parser.add_argument("--debug", action="store_true", help="Print tool IO")
    args = parser.parse_args()

    server = create_server(
        aw_host=args.aw_host, aw_port=args.aw_port, debug=args.debug
    )
    server.run(transport="http", port=args.port)

