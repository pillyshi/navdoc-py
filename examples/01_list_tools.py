"""MCP サーバが公開しているツール一覧を表示する。"""
import asyncio
from dotenv import load_dotenv
from navdoc import NavdocClient

load_dotenv()


async def main() -> None:
    client = NavdocClient()
    tools = await client.list_tools()

    print(f"{len(tools)} tools available:")
    for tool in tools:
        print(f"\n  {tool.name}")
        print(f"    {tool.description}")


asyncio.run(main())
