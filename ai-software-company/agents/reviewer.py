from agents.base import AgentResult, BaseAgent
from agents.roles import REVIEWER


class ReviewerAgent(BaseAgent):
    def __init__(self):
        super().__init__(REVIEWER)

    def review(
        self,
        task: str,
        plan: str,
        code: str,
        memory_context: str = "",
    ) -> AgentResult:
        mem = f"\n\n{memory_context}\n" if memory_context else ""
        user = f"""## Original task

{task}

## Plan

{plan}

## Code

{code}
{mem}
Review now. Flag if the work contradicts prior company memory."""
        return self.run(user)

    def _run_offline(self, user_message: str) -> str:
        has_code = "def " in user_message or "class " in user_message
        has_plan = "Implementation steps" in user_message or "### Goal" in user_message
        has_mem = "Shared company memory" in user_message
        verdict = "APPROVE" if has_code and has_plan else "REQUEST_CHANGES"
        mem_line = (
            "- Shared memory was provided for consistency checks.\n"
            if has_mem
            else ""
        )
        return f"""### Strengths
- Plan and code artifacts present for review.
{mem_line}- Offline reviewer applied checklist.

### Issues
- Offline mode cannot deep-check runtime behavior or security against live APIs.
- Confirm secrets are never hardcoded before production.

### Suggestions
- Add unit tests for validation failures.
- Add logging around auth / error boundaries if applicable.

### Verdict
{verdict} — structural review only (offline agent mode).
"""


reviewer_agent = ReviewerAgent()
