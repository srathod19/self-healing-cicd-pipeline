from typing import TypedDict, Annotated, Optional
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from agent.nodes import (
    detect_failure,
    classify_error,
    reason_and_patch,
    confidence_check,
    apply_fix,
    escalate,
)


class AgentState(TypedDict):
    run_id: str
    repo: str
    branch: str
    workflow: str
    raw_logs: str
    error_type: Optional[str]
    error_detail: Optional[str]
    patch: Optional[str]
    patch_file: Optional[str]
    confidence: Optional[float]
    reasoning: Optional[str]
    outcome: Optional[str]  # "fixed" | "escalated" | "failed"
    pr_url: Optional[str]
    messages: Annotated[list, add_messages]


def route_after_confidence(state: AgentState):
    if state.get("confidence", 0) >= 0.75:
        return "apply_fix"
    return "escalate"


def build_graph():
    g = StateGraph(AgentState)

    g.add_node("detect_failure", detect_failure)
    g.add_node("classify_error", classify_error)
    g.add_node("reason_and_patch", reason_and_patch)
    g.add_node("confidence_check", confidence_check)
    g.add_node("apply_fix", apply_fix)
    g.add_node("escalate", escalate)

    g.set_entry_point("detect_failure")
    g.add_edge("detect_failure", "classify_error")
    g.add_edge("classify_error", "reason_and_patch")
    g.add_edge("reason_and_patch", "confidence_check")
    g.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {"apply_fix": "apply_fix", "escalate": "escalate"},
    )
    g.add_edge("apply_fix", END)
    g.add_edge("escalate", END)

    return g.compile()


agent_graph = build_graph()
