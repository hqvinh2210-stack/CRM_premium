from langgraph.graph import StateGraph

from graph.state import ProjectState


def coding_node(state: ProjectState) -> ProjectState:
    print(state["task"])
    return state


builder = StateGraph(ProjectState)

builder.add_node(
    "coding",
    coding_node,
)

builder.set_entry_point("coding")
builder.set_finish_point("coding")

graph = builder.compile()


if __name__ == "__main__":
    graph.invoke(
        {
            "task": "Create Login API",
        }
    )
