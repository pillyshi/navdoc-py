"""ask() で Q&A — 最もシンプルな使い方。"""
import asyncio
from dotenv import load_dotenv
from navdoc import NavdocClient

load_dotenv()

QUESTION = "このドキュメントで最初にやるべきことは何ですか？"


async def main() -> None:
    client = NavdocClient()
    response = await client.ask(QUESTION)

    print(response.answer)
    print(f"\n[{response.model} | in={response.usage['input_tokens']} out={response.usage['output_tokens']}]")


asyncio.run(main())
