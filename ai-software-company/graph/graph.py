from langgraph.graph import END, START, StateGraph

from graph.nodes import coding_node, memory_node, planner_node, review_node
from graph.state import ProjectState


def build_graph():
    """
    Multi-agent pipeline with shared memory:

        START → memory → planner (Ava) → coder (Rex) → reviewer (Kai) → END
    """
    builder = StateGraph(ProjectState)

    builder.add_node("memory", memory_node)
    builder.add_node("planner", planner_node)
    builder.add_node("coding", coding_node)
    builder.add_node("review", review_node)

    builder.add_edge(START, "memory")
    builder.add_edge("memory", "planner")
    builder.add_edge("planner", "coding")
    builder.add_edge("coding", "review")
    builder.add_edge("review", END)

    return builder.compile()


graph = build_graph()


if __name__ == "__main__":
    result = graph.invoke(
        {
            "task": "Create Login API",
            "logs": [],
        }
    )
    print("--- result ---")
    print("status:", result.get("status"))
    print("run_id:", result.get("run_id"))
    print("modes:", result.get("agent_modes"))
    print("memory_hits:", len(result.get("memory_hits") or []))
    print("logs:", result.get("logs"))
    print("\n== memory_context ==\n", (result.get("memory_context") or "")[:500])
    print("\n== plan ==\n", (result.get("plan") or "")[:400])
