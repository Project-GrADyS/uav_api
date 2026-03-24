import asyncio

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage

from uav_agent.agent import create_agent
from uav_agent.config import MCP_SERVER_URL, MODEL_NAME, SYSTEM_PROMPT


def print_agent_response(messages: list):
    """Print the agent's latest response and any tool calls that were made."""
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                args_str = ", ".join(f"{k}={v}" for k, v in tc["args"].items())
                print(f"  [tool] {tc['name']}({args_str})")
        elif isinstance(msg, ToolMessage):
            content = msg.content
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"  [result] {content}")

    # Print the final text response
    last = messages[-1]
    if isinstance(last, AIMessage) and last.content and not last.tool_calls:
        print(f"\nAgent: {last.content}")


async def chat_loop():
    print(f"Connecting to MCP server at {MCP_SERVER_URL}...")
    client, graph = await create_agent(MCP_SERVER_URL, MODEL_NAME, SYSTEM_PROMPT)

    async with client:
        print("Connected. Type 'quit' to exit.\n")
        messages = []

        while True:
            try:
                user_input = input("You: ")
            except (EOFError, KeyboardInterrupt):
                break

            if user_input.strip().lower() in ("quit", "exit"):
                break
            if not user_input.strip():
                continue

            messages.append(HumanMessage(content=user_input))

            try:
                result = await graph.ainvoke({"messages": messages})
                new_messages = result["messages"][len(messages):]
                messages = result["messages"]
                print_agent_response(new_messages)
            except Exception as e:
                print(f"\nError: {e}")

    print("Disconnected.")


def main():
    asyncio.run(chat_loop())


if __name__ == "__main__":
    main()
