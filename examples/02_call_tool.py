"""list_tools() でツール名を確認してから call_tool() で直接呼ぶ。"""
import asyncio
import json
from dotenv import load_dotenv
from navdoc import NavdocClient

load_dotenv()

QUERY = "getting started"


async def main() -> None:
    client = NavdocClient()

    tools = await client.list_tools()
    tool_names = [t.name for t in tools]
    print(f"Available tools: {tool_names}")

    if "search" not in tool_names:
        print("'search' tool not found — adjust QUERY or tool name.")
        return

    results = await client.call_tool("search", {"query": QUERY, "top_k": 3})
    print(f"\nsearch('{QUERY}') returned {len(results)} result(s):")
    print(json.dumps(results, ensure_ascii=False, indent=2))


asyncio.run(main())
