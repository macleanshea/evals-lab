"""τ²-bench airline with our own agent guidance, everything else from the inspect-evals port.

Same tasks, customer simulator, tools and grader as `inspect_evals/tau2_airline`. The only
change is the agent's system prompt: after the port's instructions and the airline policy
we append `inspect/prompts/airline_<prompt>.md` as an <additional_guidance> block. The
policy itself is never changed (that would change what the right answer is).

prompt="v0" adds nothing, so the agent's prompt is identical to the port's.

Run: inspect eval inspect/tau2_custom.py@tau2_airline_custom -T prompt=v1 ...
"""
import pathlib

from inspect_ai import Task, task

from inspect_evals.tau2.airline.agents import get_domain_policy
from inspect_evals.tau2.airline.dataset import read_dataset
from inspect_evals.tau2.airline.scorer import airline_scorer
from inspect_evals.tau2.airline.tools import all_airline_tools
from inspect_evals.tau2.common.agents import (
    CustomerServiceAgentConfig,
    get_user_simulator_agent,
)

PROMPTS = pathlib.Path(__file__).parent / "prompts"
# Must match the port's instance name: the store keys (and slim_log.py) depend on it.
INSTANCE = "AirlineAgent"


def guidance(prompt: str) -> str:
    if prompt == "v0":
        return ""
    text = (PROMPTS / f"airline_{prompt}.md").read_text(encoding="utf-8").strip()
    return f"\n<additional_guidance>\n{text}\n</additional_guidance>"


@task
def tau2_airline_custom(
    prompt: str = "v0", shuffle: bool = False, message_limit: int | None = None
) -> Task:
    extra = guidance(prompt)
    return Task(
        dataset=read_dataset(INSTANCE, shuffle=shuffle),
        solver=get_user_simulator_agent(
            config=CustomerServiceAgentConfig(
                get_domain_policy=lambda: get_domain_policy() + extra,
                tools=[t() for t in all_airline_tools],
                instance=INSTANCE,
            ),
            message_limit=message_limit,
        ),
        scorer=airline_scorer(),
        metadata={"agent_prompt": prompt},
    )
