from typing import Annotated, Sequence, TypedDict
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from app.core.llm import get_llm
from datetime import datetime, timezone, timedelta

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_node: str

from langgraph.prebuilt import create_react_agent
from app.tools.retrieval import campus_data, latest_announcements
from app.tools.google_search import google_search_tool

def get_base_instructions() -> str:
    ist = timezone(timedelta(hours=5, minutes=30))
    current_time = datetime.now(ist).strftime('%A, %Y-%m-%d %H:%M:%S')
    return (
        f"You are RAGnarok, an advanced AI assistant for IIT Ropar. The current time is {current_time}.\n"
        "You were developed by the Iota Cluster 2025-26 (AI Club, IIT Ropar).\n"
        "Keep your answers helpful, accurate, and concise. "
        "When dealing with student entry numbers, recognize these standard IIT Ropar branch codes: "
        "CHB (Chemical), CEB (Civil), CSB (Computer Science), EEB (Electrical), HSB (Humanities), "
        "MEB (Mechanical), MMB (Metallurgical & Materials), EPB (Engineering Physics), "
        "MCB (Math & Computing), and AIB (AI & Data Engineering).\n"
    )

async def single_agent_node(state: AgentState):
    # Estimate tokens: ~4 characters per token + 800 tokens for system prompt and tools
    total_chars = sum(len(str(m.content)) for m in state["messages"]) if state.get("messages") else 0
    estimated_tokens = (total_chars // 4) + 800
    
    llm = get_llm(estimated_tokens=estimated_tokens)
    
    examples = """
Examples of how to act:

Input: "Who is the director of IIT Ropar?"
Thought: Static fact about the institute.
Action: Use campus_data tool.

Input: "Any holidays this month?"
Thought: Recent schedule and events.
Action: Use latest_announcements tool with input "holiday calendar".

Input: "What happened recently in the world?"
Thought: Real Time info & Fallback.
Action: Use google_search_tool with input "world news".

Input: "Hello!"
Thought: Greeting. No tool needed.
Action: Answer directly with a greeting.

Input: "how do u know this?"
Thought: The user is asking about the source of my previous response. I have this in my conversation history.
Action: Answer directly that the information was retrieved from the campus database or the relevant source.

Input: "Which branch is 2023MEB1456"
Thought: Entry number analysis. MEB refers to Mechanical Engineering.
Action: Answer directly that it is Mechanical Engineering.
"""

    prompt = get_base_instructions() + (
        "You have access to tools for querying academic guidelines, campus information, and Google Search.\n"
        "CRITICAL INSTRUCTION: NEVER hallucinate or provide factual information from your own internal knowledge.\n"
        "CRITICAL INSTRUCTION ON TOOLS:\n"
        "- ONLY use tools if the user is asking a NEW question for information you do not already have in your conversation history.\n"
        "- Your previous responses in the chat history were generated using your tools. If the user asks 'how do you know this?' or 'where did you find this?', you should look at your previous response and confidently answer that you retrieved it from the campus database, emails, or Google Search, WITHOUT calling any tools again.\n"
        "- For follow-up questions (e.g., 'tell me more'), DO NOT USE TOOLS if the context is already in the chat history. Just answer directly based on previous messages.\n"
        "- For conversational queries (greetings, simple questions, branch code queries), DO NOT USE TOOLS. Answer directly immediately.\n"
        "- After using a tool, you MUST formulate a final answer in text. NEVER return an empty response.\n"
        "When choosing a tool to use, follow these explicit rules based on the user's request:\n"
        "- MUST use 'latest_announcements' tool for: Mess menu, food schedules, and any recent details found through campus emails.\n"
        "- MUST use 'campus_data' tool for: Long-term campus details, positions, boards, academic guidelines, and static facts.\n"
        "- MUST use 'google_search_tool' for: Everything else (world news, general knowledge, etc) or as a final fallback.\n"
        "IMPORTANT: If you find sufficient information, DO NOT call subsequent tools. STOP searching and answer the user immediately.\n"
        "If all relevant tools return no information, admit that you do not know and advise the user to visit the official IIT Ropar website (https://www.iitrpr.ac.in).\n"
        "CRITICAL: You are strictly limited to MAXIMUM 2 tool calls per query. If you do not find the answer after 2 tool calls, you MUST stop and tell the user you cannot find it.\n"
        "When using retrieval tools, try to choose minimal, targeted keywords.\n\n"
        + examples
    )
    agent = create_react_agent(
        llm, 
        tools=[campus_data, latest_announcements, google_search_tool],
        prompt=prompt
    )
    
    try:
        result = await agent.ainvoke({"messages": state["messages"]}, {"recursion_limit": 6})
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Agent recursion limit hit: {e}")
        return {"messages": [AIMessage(content="I searched my database extensively but couldn't pinpoint the exact information. Could you try rephrasing or narrowing down your request?")], "next_node": "general_agent"}
        
    # Check if a tool was called to populate next_node context if needed by frontend
    route = "general_agent"
    last_msg = result["messages"][-1]
    
    for msg in result["messages"]:
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "campus_data":
                    route = "academic_agent"
                elif tc["name"] == "latest_announcements":
                    route = "campus_agent"
                elif tc["name"] == "google_search_tool":
                    route = "general_agent"  # Web searches can just display as core agent

    return {"messages": [last_msg], "next_node": route}

# Define the graph
workflow = StateGraph(AgentState)

workflow.add_node("agent", single_agent_node)
workflow.set_entry_point("agent")
workflow.add_edge("agent", END)

app_graph = workflow.compile()

