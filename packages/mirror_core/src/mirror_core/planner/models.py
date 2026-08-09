"""Planner data models: compiled steps and the immutable execution plan."""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mirror_core.exceptions import PlannerError
from mirror_core.execution import ExecutionPolicy
from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.pipeline import Step


class CompiledStep(BaseModel):
    """A step with capability and provider identities resolved at compile time."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    definition: Step
    capability: CapabilityManifest
    provider: ProviderManifest
    dependencies: frozenset[str] = Field(default_factory=frozenset)
    fallback_providers: tuple[ProviderManifest, ...] = Field(default_factory=tuple)
    policy: ExecutionPolicy = Field(default_factory=ExecutionPolicy)

    @property
    def id(self) -> str:
        return self.definition.id


class ExecutionPlan(BaseModel):
    """Immutable plan consumed by the executor."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    pipeline_id: str
    steps: Mapping[str, CompiledStep]
    order: tuple[str, ...]
    parallel_groups: tuple[tuple[str, ...], ...]
    config_fingerprint: str
    input_names: frozenset[str] = Field(default_factory=frozenset)

    def model_post_init(self, __context: Any, /) -> None:
        """Freeze the compiled steps mapping after validation."""
        object.__setattr__(self, "steps", MappingProxyType(dict(self.steps)))

    def get_step(self, step_id: str) -> CompiledStep:
        try:
            return self.steps[step_id]
        except KeyError as exc:
            raise PlannerError(f"Unknown compiled step: {step_id}") from exc

    @property
    def step_ids(self) -> list[str]:
        return list(self.order)

    @property
    def dependencies(self) -> Mapping[str, frozenset[str]]:
        return MappingProxyType({step_id: frozenset(step.dependencies) for step_id, step in self.steps.items()})

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "steps": {
                step_id: {
                    "definition": compiled.definition.model_dump(mode="json"),
                    "capability": compiled.capability.name,
                    "capability_version": compiled.capability.api_version,
                    "provider": compiled.provider.name,
                    "fallback_providers": [provider.name for provider in compiled.fallback_providers],
                    "dependencies": sorted(compiled.dependencies),
                    "policy": compiled.policy.model_dump(mode="json"),
                }
                for step_id, compiled in self.steps.items()
            },
            "order": list(self.order),
            "parallel_groups": [list(group) for group in self.parallel_groups],
            "config_fingerprint": self.config_fingerprint,
            "input_names": sorted(self.input_names),
        }
