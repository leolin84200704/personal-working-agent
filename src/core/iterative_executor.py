"""
Iterative Executor - 讓 Agent 能自我修正和快速迭代

這是讓 Agent 像 Claude 一樣快速反應的關鍵
"""

from anthropic import Anthropic
from .markdown_executor import MarkdownExecutor


class IterativeExecutor(MarkdownExecutor):
    """
    增強版 MarkdownExecutor，支援自我修正和快速迭代
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_iterations = 5  # 最多嘗試 5 次

    async def execute_with_retry(self, ticket, action_description: str) -> dict:
        """
        執行任務，遇到錯誤自動修正並重試

        這是讓 Agent 像 Claude 一樣能夠：
        1. 寫 code
        2. 執行
        3. 看錯誤
        4. 自動修正
        5. 重試
        全部在單一次呼叫中完成！
        """
        iteration = 0
        context = []
        last_error = None

        while iteration < self.max_iterations:
            iteration += 1

            if iteration == 1:
                # 第一次：執行原始任務
                prompt = f"{action_description}\n\n請執行這個任務。"
            else:
                # 後續：根據錯誤修正
                prompt = f"""
之前的嘗試失敗了。請修正錯誤並重試。

**原始任務:**
{action_description}

**錯誤訊息:**
{last_error}

**已執行的步驟:**
{chr(10).join(f"- {step}" for step in context)}

請提供修正後的執行計畫。
                """

            # 請 LLM 產生執行計畫
            plan_response = self.claude.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4000,
                messages=[{"role": "user", "content": prompt}]
            )

            plan_text = plan_response.content[0].text

            # 執行計畫
            result = await self._execute_plan_from_text(plan_text)

            if result.get("success"):
                return {
                    "success": True,
                    "iterations": iteration,
                    "output": result.get("output"),
                    "message": f"✅ 在 {iteration} 次嘗試後成功"
                }

            # 記錄錯誤並重試
            last_error = result.get("error", "Unknown error")
            context.append(f"嘗試 {iteration}: {last_error}")

        return {
            "success": False,
            "iterations": iteration,
            "error": last_error,
            "message": f"❌ 在 {iteration} 次嘗試後仍然失敗"
        }

    async def _execute_plan_from_text(self, plan_text: str) -> dict:
        """
        從 LLM 產生的文字計畫中提取並執行動作
        """
        import json
        import re

        # 解析 action (簡化版，實際需要更複雜的解析)
        actions = self._parse_actions(plan_text)

        for action in actions:
            action_type = action.get("action")
            params = action.get("params", {})

            if action_type == "write_file":
                result = self._write_file(
                    params.get("path"),
                    params.get("content", "")
                )
                if not result.get("success"):
                    return {"success": False, "error": result.get("error")}

            elif action_type == "run_bash":
                result = self._run_bash(
                    params.get("command", ""),
                    timeout=30
                )
                if not result.get("success"):
                    return {
                        "success": False,
                        "error": result.get("stderr") or result.get("error")
                    }

        return {"success": True}

    def _parse_actions(self, text: str) -> list:
        """
        從 LLM 回應中提取 action JSON
        """
        import json
        import re

        actions = []

        # 尋找 JSON code blocks
        json_pattern = r'```json\s*(\[.*?\])\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)

        for match in matches:
            try:
                actions.extend(json.loads(match))
            except json.JSONDecodeError:
                continue

        return actions


# 使用範例：
#
# async def main():
#     executor = IterativeExecutor()
#
#     result = await executor.execute_with_retry(
#         ticket=None,
#         action_description="""
#         1. 建立 scripts/batch-insert-vp15874.ts
#         2. 執行它
#         3. 驗證結果
#         """
#     )
#
#     print(result["message"])
#     print(result["output"])
