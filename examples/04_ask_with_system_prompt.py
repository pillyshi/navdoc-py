"""system_prompt をカスタマイズして回答スタイルを変える。"""
import asyncio
from dotenv import load_dotenv
from navdoc import NavdocClient

load_dotenv()

SYSTEM_PROMPT = """\
あなたは社内ドキュメントの QA アシスタントです。
- 必ずドキュメントの記述に基づいて回答してください。
- 根拠が見つからない場合は「ドキュメントに記載がありません」と答えてください。
- 回答は箇条書きで簡潔にまとめてください。
"""

QUESTION = "認証の設定手順を教えてください。"


async def main() -> None:
    client = NavdocClient()
    response = await client.ask(
        QUESTION,
        system_prompt=SYSTEM_PROMPT,
        top_k=5,
    )

    print(response.answer)


asyncio.run(main())
