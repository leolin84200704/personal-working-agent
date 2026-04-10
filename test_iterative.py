"""
Test the iterative executor functionality
"""
import asyncio
from anthropic import Anthropic
from dotenv import load_dotenv
from src.core.markdown_executor import MarkdownExecutor

load_dotenv()


async def test_iterative():
    """Test the execute_with_retry method"""

    executor = MarkdownExecutor()

    # Test 1: Simple write file task
    print("=" * 60)
    print("Test 1: Write a simple file")
    print("=" * 60)

    result = await executor.execute_with_retry(
        task_description="寫一個測試檔案到 /Users/hung.l/src/lis-backend-emr-v2/test-iterative.txt，內容是 'Hello from iterative executor!'"
    )

    print(f"\n{result.get('message')}")
    print(f"Output: {result.get('output')}")

    # Test 2: Write and execute TypeScript
    print("\n" + "=" * 60)
    print("Test 2: Write and execute a TypeScript script")
    print("=" * 60)

    result2 = await executor.execute_with_retry(
        task_description="""建立一個 TypeScript script 在 scripts/test-iterative.ts，
這個 script 要：
1. import PrismaClient
2. 查詢 ehr_integrations 表的前 3 筆記錄
3. 輸出到 console

然後執行這個 script。"""
    )

    print(f"\n{result2.get('message')}")
    if result2.get('output'):
        print(f"Output:\n{result2.get('output')}")
    if result2.get('error'):
        print(f"Error: {result2.get('error')}")


if __name__ == "__main__":
    asyncio.run(test_iterative())
