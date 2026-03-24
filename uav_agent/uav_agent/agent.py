from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, MessagesState, START
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage


async def create_agent(mcp_url: str, model_name: str, system_prompt: str):
    """Create and return (client, graph) for the UAV agent.

    The caller must use `async with client:` to manage the MCP connection lifecycle.
    """
    client = MultiServerMCPClient({
        "uav": {
            "transport": "http",
            "url": mcp_url,
        }
    })

    tools = await client.get_tools()
    model = ChatAnthropic(model=model_name)

    system_message = SystemMessage(content=system_prompt)

    def call_model(state: MessagesState):
        messages = [system_message] + state["messages"]
        response = model.bind_tools(tools).invoke(messages)
        return {"messages": response}

    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", tools_condition)
    builder.add_edge("tools", "agent")
    graph = builder.compile()

    return client, graph
