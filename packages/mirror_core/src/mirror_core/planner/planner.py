"""Pipeline planner: validate and resolve runtime identities exactly once."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from mirror_core.exceptions import PlannerError
from mirror_core.execution import ExecutionPolicy
from mirror_core.extensions.models import CapabilityManifest, ProviderManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.imports import resolve_type
from mirror_core.pipeline import Pipeline
from mirror_core.planner.graph import (
    binding_source_step,
    build_dependency_graph,
    compute_parallel_groups,
    iter_binding_sources,
    topological_sort,
)
from mirror_core.planner.models import CompiledStep, ExecutionPlan


class Planner:
    """Validate a pipeline and resolve all runtime identities exactly once."""

    def __init__(
        self,
        registry: ExtensionRegistryManager,
        default_providers: dict[str, str] | None = None,
    ) -> None:
        self._registry = registry
        self._default_providers = default_providers or {}

    def plan(self, pipeline: Pipeline) -> ExecutionPlan:
        self._validate_unique_step_ids(pipeline)
        capabilities = self._resolve_capabilities(pipeline)
        self._validate_required_capabilities(capabilities)
        providers = self._resolve_providers(pipeline, capabilities)
        fallback_providers = self._resolve_fallback_providers(pipeline, capabilities, providers)
        dependencies, reverse_dependencies = build_dependency_graph(pipeline)
        order = topological_sort(pipeline, dependencies, reverse_dependencies)
        self._validate_bindings(pipeline, capabilities)

        groups = compute_parallel_groups(dependencies, order)

        compiled_steps = {
            step.id: CompiledStep(
                definition=step,
                capability=capabilities[step.id],
                provider=providers[step.id],
                dependencies=frozenset(dependencies[step.id]),
                fallback_providers=tuple(fallback_providers[step.id]),
                policy=ExecutionPolicy.from_step(step),
            )
            for step in pipeline.steps
        }
        fingerprint_payload = pipeline.model_dump(mode="json")
        fingerprint_payload["resolved_providers"] = {
            step_id: {
                "capability": compiled.capability.name,
                "capability_version": compiled.capability.api_version,
                "provider": compiled.provider.name,
                "provider_version": compiled.provider.metadata.get("version"),
            }
            for step_id, compiled in compiled_steps.items()
        }
        fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ExecutionPlan(
            pipeline_id=pipeline.id,
            steps=compiled_steps,
            order=tuple(order),
            parallel_groups=tuple(tuple(group) for group in groups),
            config_fingerprint=fingerprint,
            input_names=frozenset(pipeline.inputs),
        )

    @staticmethod
    def _validate_unique_step_ids(pipeline: Pipeline) -> None:
        step_ids = [step.id for step in pipeline.steps]
        duplicates = sorted({step_id for step_id in step_ids if step_ids.count(step_id) > 1})
        if duplicates:
            raise PlannerError(f"Duplicate pipeline step IDs: {', '.join(duplicates)}")

    def _resolve_capabilities(self, pipeline: Pipeline) -> dict[str, CapabilityManifest]:
        resolved: dict[str, CapabilityManifest] = {}
        for step in pipeline.steps:
            try:
                resolved[step.id] = self._registry.resolve_capability(step.capability)
            except Exception as exc:
                raise PlannerError(
                    f"Unknown capability {step.capability!r} in step {step.id!r}",
                    cause=exc,
                ) from exc
        return resolved

    def _validate_required_capabilities(self, capabilities: dict[str, CapabilityManifest]) -> None:
        required = sorted({(dependency.target, dependency.version_constraint) for capability in capabilities.values() for dependency in capability.dependencies})
        for dependency_name, dependency_version in required:
            try:
                self._registry.resolve_capability(dependency_name, dependency_version)
            except Exception as exc:
                constraint = dependency_version if dependency_version is not None else "any version"
                raise PlannerError(
                    f"Required capability {dependency_name!r} ({constraint}) is not available",
                    cause=exc,
                ) from exc

    def _resolve_providers(
        self,
        pipeline: Pipeline,
        capabilities: dict[str, CapabilityManifest],
    ) -> dict[str, ProviderManifest]:
        resolved: dict[str, ProviderManifest] = {}
        for step in pipeline.steps:
            requested = step.provider or self._default_providers.get(step.capability)
            try:
                resolved[step.id] = self._registry.resolve_provider(capabilities[step.id], requested)
            except Exception as exc:
                raise PlannerError(
                    f"Unable to resolve provider for step {step.id!r} ({step.capability!r})",
                    cause=exc,
                ) from exc
        return resolved

    def _resolve_fallback_providers(
        self,
        pipeline: Pipeline,
        capabilities: dict[str, CapabilityManifest],
        primary: dict[str, ProviderManifest],
    ) -> dict[str, list[ProviderManifest]]:
        resolved: dict[str, list[ProviderManifest]] = {}
        for step in pipeline.steps:
            fallback = step.fallback.providers if step.fallback is not None else ()
            providers: list[ProviderManifest] = []
            seen: set[str] = set()
            for provider_name in fallback:
                if provider_name in seen or provider_name == primary[step.id].name:
                    continue
                try:
                    provider = self._registry.resolve_provider(capabilities[step.id], provider_name)
                except Exception as exc:
                    raise PlannerError(
                        f"Unable to resolve fallback provider {provider_name!r} for step {step.id!r}",
                        cause=exc,
                    ) from exc
                providers.append(provider)
                seen.add(provider.name)
            resolved[step.id] = providers
        return resolved

    def _validate_bindings(
        self,
        pipeline: Pipeline,
        capabilities: dict[str, CapabilityManifest],
    ) -> None:
        steps_by_id = {step.id: step for step in pipeline.steps}
        for step in pipeline.steps:
            capability = capabilities[step.id]
            available_outputs = set(capability.output_ports)
            result_model = resolve_type(capability.result_model)
            if result_model is not None:
                available_outputs.update(getattr(result_model, "model_fields", {}).keys())
                available_outputs.add("result")
            unknown_outputs = sorted(set(step.outputs).difference(available_outputs))
            if unknown_outputs:
                raise PlannerError(f"Step {step.id!r} declares unknown outputs: {', '.join(unknown_outputs)}")
            declared_inputs = set(capability.input_ports)
            request_model = resolve_type(capability.request_model)
            if not declared_inputs and request_model is not None:
                declared_inputs = set(getattr(request_model, "model_fields", {}).keys())

            for target, source in step.input.items():
                if declared_inputs and target not in declared_inputs:
                    raise PlannerError(f"Step {step.id!r} binds undeclared input port {target!r}")
                for binding in iter_binding_sources(source):
                    source_step = binding_source_step(binding, steps_by_id)
                    if source_step is None:
                        continue
                    if source_step == "$pipeline":
                        source_output = binding[len("$pipeline.") :]
                        if source_output not in pipeline.inputs:
                            raise PlannerError(f"Step {step.id!r} references undeclared pipeline input {source_output!r}")
                        continue
                    source_output = binding.split(".", 1)[1]
                    source_capability = capabilities[source_step]
                    source_ports = set(source_capability.output_ports)
                    source_result_model = resolve_type(source_capability.result_model)
                    if source_result_model is not None:
                        source_ports.update(getattr(source_result_model, "model_fields", {}).keys())
                        source_ports.add("result")
                    if not source_ports:
                        source_ports = set(steps_by_id[source_step].outputs)
                    first_output = source_output.split(".", 1)[0]
                    if first_output not in source_ports:
                        raise PlannerError(f"Step {step.id!r} references unknown output {source_output!r} from step {source_step!r}")
                    self._validate_port_compatibility(
                        source_step,
                        first_output,
                        source_capability,
                        step.id,
                        target,
                        capability,
                    )

    @staticmethod
    def _validate_port_compatibility(
        source_step: str,
        source_output: str,
        source_capability: CapabilityManifest,
        target_step: str,
        target_input: str,
        target_capability: CapabilityManifest,
    ) -> None:
        source_type: Any = source_capability.output_ports.get(source_output)
        source_result_model = resolve_type(source_capability.result_model)
        if source_type is None and source_result_model is not None:
            field = getattr(source_result_model, "model_fields", {}).get(source_output)
            source_type = field.annotation if field is not None else None
        target_type: Any = target_capability.input_ports.get(target_input)
        target_request_model = resolve_type(target_capability.request_model)
        if target_type is None and target_request_model is not None:
            field = getattr(target_request_model, "model_fields", {}).get(target_input)
            target_type = field.annotation if field is not None else None
        if source_type is None or target_type is None or source_type == target_type:
            return
        if source_type is Any or target_type is Any:
            # An Any side (e.g. a transform step value) is compatible with any
            # binding; the target model validates the value at runtime.
            return
        if isinstance(source_type, type) and isinstance(target_type, type) and issubclass(source_type, target_type):
            return
        source_name = getattr(source_type, "__name__", str(source_type))
        target_name = getattr(target_type, "__name__", str(target_type))
        raise PlannerError(f"Incompatible binding {source_step}.{source_output} ({source_name}) -> {target_step}.{target_input} ({target_name})")
