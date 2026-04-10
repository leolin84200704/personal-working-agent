#!/usr/bin/env python
"""
Simple WebSocket client for testing LIS Code Agent.

Usage:
    python test_client.py
"""
import asyncio
import websockets
import json


async def test_agent():
    """Test the agent with a simple conversation."""
    uri = "ws://localhost:8000/api/ws/chat"

    print("Connecting to LIS Code Agent...")
    print("=" * 60)

    try:
        async with websockets.connect(uri) as websocket:
            # Receive welcome message
            welcome = await websocket.recv()
            print(f"Agent: {json.loads(welcome).get('content', 'Welcome!')}")

            # Test questions
            questions = [
                "你好，我是 Leo",
                "幫我看看有哪些新的 Jira ticket",
                "我的 repos 有哪些？",
            ]

            for question in questions:
                print(f"\n{'=' * 60}")
                print(f"You: {question}")

                # Send question
                await websocket.send(json.dumps({"message": question}))

                # Receive response
                response = await websocket.recv()
                data = json.loads(response)

                if data.get("type") == "response":
                    print(f"\nAgent: {data.get('content', '')}")
                    if data.get("thoughts"):
                        print(f"\n[Thought Process]")
                        for thought in data.get("thoughts", []):
                            print(f"  {thought}")
                elif data.get("type") == "error":
                    print(f"\nError: {data.get('content', '')}")

            print("\n" + "=" * 60)
            print("Test completed!")

    except websockets.exceptions.WebSocketException as e:
        print(f"WebSocket error: {e}")
        print("\nMake sure the agent service is running:")
        print("  python start_agent.py")
    except ConnectionRefusedError:
        print("Could not connect to the agent service.")
        print("Make sure it's running: python start_agent.py")


if __name__ == "__main__":
    asyncio.run(test_agent())
