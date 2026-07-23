from agents.base import AgentResult, BaseAgent
from agents.roles import PLANNER


class PlannerAgent(BaseAgent):
    def __init__(self):
        super().__init__(PLANNER)

    def plan(self, task: str, memory_context: str = "") -> AgentResult:
        mem = f"\n\n{memory_context}\n" if memory_context else ""
        user = f"""## Task from Linear / user

{task}
{mem}
Produce the implementation plan now. Respect shared company memory when relevant."""
        return self.run(user)

    def _run_offline(self, user_message: str) -> str:
        task = user_message
        if "## Task" in user_message:
            task = user_message.split("## Task", 1)[-1].strip()
            lines = [ln for ln in task.splitlines() if ln.strip()]
            if lines and lines[0].lower().startswith("from "):
                lines = lines[1:]
            # stop at memory section or instruction
            cut = []
            for ln in lines:
                low = ln.strip().lower()
                if low.startswith("## shared company memory"):
                    break
                if low.startswith("produce the implementation"):
                    break
                cut.append(ln)
            task = "\n".join(cut).strip() or task

        mem_note = (
            "- Used shared memory context when present\n"
            if "Shared company memory" in user_message
            else ""
        )

        return f"""### Goal
Deliver: {task[:200]}

### Assumptions
- Backend: Python / FastAPI
- Auth tokens: JWT (if auth-related)
- Offline planner mode
{mem_note}
### Implementation steps
1. Clarify inputs/outputs and error cases for the task.
2. Define request/response models (Pydantic).
3. Implement core handler / service logic.
4. Wire FastAPI route(s) and validation.
5. Add basic tests for happy path + one failure path.
6. Document how to run locally.

### Acceptance criteria
- [ ] Endpoint or module fulfills the stated task
- [ ] Validation rejects bad input
- [ ] Happy path returns expected shape

### Risks / open questions
- Confirm auth provider and storage if credentials are involved.
"""


planner_agent = PlannerAgent()
