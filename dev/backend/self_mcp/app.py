import asyncio
import os
import sys
import json
from contextlib import AsyncExitStack
from typing import Any
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from openai import AzureOpenAI

load_dotenv()

class MCPClient:
    """個別のMCPサーバーとの接続を管理するクラス"""

    def __init__(self, server_name: str, server_path: str):
        self.server_name = server_name
        self.server_path = server_path
        self.session = None
        self.exit_stack = None
        self.tools = []
        self.tool_server_map = {}
    
    async def opening(self):
        if self.exit_stack:
            await self.exit_stack.aclose()
        self.exit_stack = AsyncExitStack()
        server_params = StdioServerParameters(
            command=sys.executable,
            args=["-u", self.server_path],
            env={"PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}
        )

        # サーバープロセスを起動し、標準入出力経由でMCPサーバーと非同期に接続しセッションを初期化
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )
        await self.session.initialize()
    
    async def closing(self):
        if self.exit_stack:
            await self.exit_stack.aclose()

    async def get_tool_list(self) -> str:
        """MCPサーバーに接続し、利用可能なツールを取得"""
        await self.opening()

        # サーバーから利用可能なツール一覧を取得
        response = await self.session.list_tools()
        self.tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        self.tool_server_map = {tool.name: self.server_name for tool in response.tools}
        tool_names = [tool["name"] for tool in self.tools]

        await self.closing()

        return f"{self.server_name}と接続しました。利用可能なツール: {', '.join(tool_names)}"

class MultiMCPManager:
    def __init__(self):
        self.clients = [
            MCPClient("mcp_os_name", os.getenv("MCP_OS_NAME_PATH")),
            MCPClient("mcp_disk_usage", os.getenv("MCP_DISK_USAGE_PATH"))
        ]
        self.agent = AzureOpenAI(
            azure_endpoint=os.getenv("ENDPOINT_URL"),
            api_key=os.getenv("API_KEY"),
            api_version=os.getenv("API_VERSION"),
        )
        self.all_tools = []
        self.tool_to_client = {}
        self.model_name = os.getenv("DEPLOYMENT_NAME")

    async def get_tool_list(self) -> str:
        """全サーバーへの接続"""
        results = []
        for client in self.clients:
            result = await self._get_tools(client)
            results.append(result)
        return "\n".join(str(result) for result in results)

    async def _get_tools(self, client: MCPClient) -> str:
        """個別のクライアント接続処理"""
        try:
            result = await client.get_tool_list()
            for tool in client.tools:
                tool = self.make_tool(tool)
                self.all_tools.append(tool)
            for tool_name in client.tool_server_map:
                self.tool_to_client[tool_name] = client
            return result
        except Exception as e:
            return f"Failed to connect to {client.server_path} server: {str(e)}"
    
    def make_tool(self, tool):
        return {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": {
                    "type": "object",
                    "properties": tool["input_schema"]["properties"],
                    "required": tool["input_schema"]["required"]
                }
            }
        }

    async def process_message(
            self,
            message: str,
            history: list[dict[str, Any]]
    ) -> tuple:
        new_messages = await self._process_query(message, history)
        # チャット履歴を更新
        updated_history = history + [{"role": "user", "content": message}] + new_messages
        # textbox_reset = gr.Textbox(value="")
        return updated_history, new_messages

    async def _process_query(
            self,
            message: str,
            history: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        messages = []
        for msg in history:
            role, content = msg.get("role"), msg.get("content")

            if role in ["user", "assistant", "system"]:
                messages.append({"role": role, "content": content})

        messages.append({"role": "user", "content": message})

        # ユーザーからの質問を使用可能なツール情報を含めて、Claude API用の形式に変換して送信
        response = self.agent.chat.completions.create(
            model=self.model_name,
            max_tokens=1024,
            messages=messages,
            tools=self.all_tools,
            tool_choice="auto"
        )
        result_messages = []

        # Claude APIからの応答を処理
        for choice in response.choices:
            if choice.finish_reason == 'stop':
                result_messages.append({
                    "role": "assistant",
                    "content": choice.message.content
                })
            elif choice.finish_reason == 'tool_calls':
                for tool in choice.message.tool_calls:
                    tool_name = tool.function.name
                    tool_args = json.loads(tool.function.arguments)
                    client = self.tool_to_client.get(tool_name)
                    await client.opening()

                    # Claude API から使用を提示されたツールを実行
                    client = self.tool_to_client.get(tool_name)
                    result = await client.session.call_tool(tool_name, tool_args)
                    await client.closing()
                    result_text = str(result.content)
                    result_messages.append({
                        "role": "assistant",
                        "content": "```\n" + result_text + "\n```",
                        "metadata": {
                            "parent_id": f"result_{tool_name}",
                            "id": f"raw_result_{tool_name}",
                            "title": "Raw Output"
                        }
                    })

                    # ツールの実行結果を含めて再度Claude API 呼び出し
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Tool result for {tool_name}:\n"
                            f"{result_text}"
                        )
                    })
                next_response = self.agent.chat.completions.create(
                    model=self.model_name,
                    max_tokens=1024,
                    messages=messages,
                )
                result_messages.append({
                    "role": "assistant",
                    "content": next_response.choices[0].message.content
                })

        return result_messages

async def main():
    """メインの非同期処理"""
    if not os.getenv("API_KEY"):
        print("Warning: API_KEY を .env ファイルに設定してください。")
    clients = MultiMCPManager()
    results = await clients.get_tool_list()
    print(results)
    results = await clients.process_message(message="yukihitoのosの名前を取得してください", history=[])
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
    # main()