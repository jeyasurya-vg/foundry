from .base import Runner, RunResult, ResumePacket
from .attended import AttendedRunner
from .anthropic_api import AnthropicAPIRunner
from .stubs import BedrockRunner, VertexRunner, OpenAIRunner, LocalRunner

RUNNERS = {
    "attended": AttendedRunner,
    "anthropic-api": AnthropicAPIRunner,
    "bedrock": BedrockRunner,
    "vertex": VertexRunner,
    "openai": OpenAIRunner,
    "local": LocalRunner,
}

__all__ = [
    "Runner", "RunResult", "ResumePacket",
    "AttendedRunner", "AnthropicAPIRunner",
    "BedrockRunner", "VertexRunner", "OpenAIRunner", "LocalRunner",
    "RUNNERS",
]
