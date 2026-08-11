"""Capability manifest for LLM (text generation)."""

from mirror_core.extensions.models import CapabilityManifest

from .models import LLMRequest, LLMResult
from .protocol import LLM
from .settings import LLMSettings

capability = CapabilityManifest(
    name="llm",
    api_version="1.0.0",
    protocol=LLM,
    request_model=LLMRequest,
    result_model=LLMResult,
    settings_model=LLMSettings,
    runner="mirror_llm.runner:llm_step",
    metadata={"summary": "LLM text generation capability"},
)
