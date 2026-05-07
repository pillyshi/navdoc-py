"""response.tool_calls で RAG の根拠（どのツールが何を検索したか）を確認する。"""
import asyncio
import json
from dotenv import load_dotenv
from navdoc import NavdocClient

load_dotenv()

QUESTION = "エラーコード 404 の対処方法を教えてください。"


async def main() -> None:
    client = NavdocClient()
    response = await client.ask(QUESTION)

    print("=== Answer ===")
    print(response.answer)

    print(f"\n=== Tool calls ({len(response.tool_calls)}) ===")
    for i, tc in enumerate(response.tool_calls, 1):
        print(f"\n[{i}] {tc.name}")
        print(f"  input:  {json.dumps(tc.input, ensure_ascii=False)}")
        output_preview = json.dumps(tc.output, ensure_ascii=False)
        if len(output_preview) > 200:
            output_preview = output_preview[:200] + "..."
        print(f"  output: {output_preview}")


asyncio.run(main())
