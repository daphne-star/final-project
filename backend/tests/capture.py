"""A deterministic model that records exactly what each agent sent it.

Using FunctionModel rather than TestModel means the tests can assert on the
real instructions string the provider would have received, which is how the
"each executive is its own agent" claim gets verified instead of assumed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic_ai.messages import (
    ModelMessage,
    ModelRequest,
    ModelResponse,
    TextPart,
    ToolCallPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel


@dataclass
class CapturedCall:
    instructions: str
    user_prompts: list[str]
    output_tool_name: str | None


@dataclass
class InstructionRecorder:
    """Records every call, and replies with a valid ConsultationResponse."""

    answer: str = "Recorded answer."
    calls: list[CapturedCall] = field(default_factory=list)

    def __call__(self, messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        instructions = ""
        prompts: list[str] = []
        for message in messages:
            if isinstance(message, ModelRequest):
                if message.instructions:
                    instructions = message.instructions
                for part in message.parts:
                    if part.part_kind == "user-prompt":
                        prompts.append(str(part.content))

        tool_name = info.output_tools[0].name if info.output_tools else None
        self.calls.append(
            CapturedCall(
                instructions=instructions, user_prompts=prompts, output_tool_name=tool_name
            )
        )

        payload = {
            "answer": self.answer,
            "key_points": ["Point one", "Point two"],
            "assumptions": [
                {
                    "statement": "Runway figure is current",
                    "why_it_matters": "The recommendation changes if it is stale",
                    "how_to_validate": "Check the latest bank balance",
                }
            ],
            "risks": [
                {
                    "description": "Execution capacity is unproven",
                    "severity": "moderate",
                    "likelihood": "medium",
                    "mitigation": "Run a two-week pilot",
                }
            ],
            "open_questions": [
                {
                    "question": "What is the current CAC payback?",
                    "why_it_matters": "It determines whether growth spend is affordable",
                    "who_should_answer": "cgo",
                }
            ],
            "recommended_actions": [
                {
                    "description": "Model the three options against runway",
                    "priority": "high",
                    "suggested_owner": "Finance",
                    "rough_timeline": "next 30 days",
                }
            ],
            "confidence_level": "medium",
            "out_of_scope": False,
            "refer_to_agent_id": None,
        }

        if tool_name:
            return ModelResponse(parts=[ToolCallPart(tool_name, payload)])
        return ModelResponse(parts=[TextPart(self.answer)])

    @property
    def last(self) -> CapturedCall:
        return self.calls[-1]

    def as_model(self) -> FunctionModel:
        return FunctionModel(self, model_name="recorder")


def recorder_model(answer: str = "Recorded answer.") -> tuple[InstructionRecorder, FunctionModel]:
    rec = InstructionRecorder(answer=answer)
    return rec, rec.as_model()
