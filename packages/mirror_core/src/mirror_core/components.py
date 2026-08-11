"""Provider component construction, validation, lookup, and lifecycle ownership."""

from __future__ import annotations

import inspect
from contextlib import AsyncExitStack
from typing import Any, get_args, get_origin, get_type_hints

from pydantic import BaseModel

from mirror_core.exceptions import ApplicationError
from mirror_core.extensions.models import CapabilityManifest
from mirror_core.extensions.registry import ExtensionRegistryManager
from mirror_core.imports import import_symbol, resolve_model, resolve_type
from mirror_core.lifecycle import AsyncLifecycle
from mirror_core.settings import MirrorSettings


class ComponentManager:
    """Own provider instances selected for one Application runtime."""

    def __init__(
        self, registry: ExtensionRegistryManager, settings: MirrorSettings
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._instances: dict[tuple[str, str], Any] = {}
        self._selected_providers: dict[str, str] = {}
        self._initializing: set[str] = set()

    @property
    def instances(self) -> dict[tuple[str, str], Any]:
        """Return the mutable runtime mapping consumed by the executor."""
        return self._instances

    async def initialize(self, stack: AsyncExitStack) -> None:
        """Construct and start all configured providers transactionally."""
        for capability_name in self._settings.components:
            await self.ensure_capability(capability_name, stack)

    async def ensure_capability(
        self, capability_name: str, stack: AsyncExitStack
    ) -> Any:
        """Ensure one capability provider instance exists, initializing dependencies first."""
        capability = self._registry.resolve_capability(capability_name)
        provider_name = self._select_provider_name(capability_name, capability)
        return await self._ensure_provider(capability_name, provider_name, stack)

    async def ensure_provider(
        self, capability_name: str, provider_name: str, stack: AsyncExitStack
    ) -> Any:
        """Ensure one explicit capability/provider pair exists."""
        return await self._ensure_provider(capability_name, provider_name, stack)

    async def _ensure_provider(
        self,
        capability_name: str,
        provider_name: str,
        stack: AsyncExitStack,
    ) -> Any:
        key = (capability_name, provider_name)
        if key in self._instances:
            self._selected_providers.setdefault(capability_name, provider_name)
            return self._instances[key]

        if capability_name in self._initializing:
            raise ApplicationError(
                f"Dependency cycle detected while initializing {capability_name!r}"
            )

        self._initializing.add(capability_name)
        try:
            capability = self._registry.resolve_capability(capability_name)
            provider = self._registry.resolve_provider(capability, provider_name)
            self._selected_providers[capability_name] = provider.name

            dependency_instances: dict[str, Any] = {}
            for dependency in capability.dependencies:
                dependency_instance = await self.ensure_capability(
                    dependency.target, stack
                )
                dependency_instances[dependency.target] = dependency_instance

            factory = import_symbol(provider.factory)
            settings_model = resolve_model(provider.settings_model)
            raw_settings = self._settings.component_settings.get(
                capability_name, {}
            ).get(provider.name, {})
            settings_instance = settings_model.model_validate(raw_settings)
            instance = self._instantiate(
                factory, settings_instance, dependency_instances
            )

            protocol = resolve_type(capability.protocol)
            if protocol is not None and not isinstance(instance, protocol):
                raise ApplicationError(
                    f"Provider {provider.name!r} does not implement capability "
                    f"protocol {capability.name!r}"
                )
            if isinstance(instance, AsyncLifecycle):
                stack.push_async_callback(instance.teardown)
                await instance.setup()
            self._instances[key] = instance
            return instance
        finally:
            self._initializing.discard(capability_name)

    def _instantiate(
        self,
        factory: Any,
        settings_instance: BaseModel,
        dependency_instances: dict[str, Any],
    ) -> Any:
        """Instantiate a provider with settings plus any protocol dependencies."""
        if inspect.isclass(factory) and not self._accepts_constructor_arguments(
            factory
        ):
            return factory()
        parameters = self._factory_parameters(factory)
        accepts_var_kwargs = any(
            parameter.kind is inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        accepts_settings = accepts_var_kwargs or "settings" in parameters
        kwargs = self._build_dependency_kwargs(factory, dependency_instances)
        if accepts_settings:
            kwargs["settings"] = settings_instance
        if kwargs:
            return factory(**kwargs)
        return factory()

    @staticmethod
    def _accepts_constructor_arguments(factory: Any) -> bool:
        """Return True when the class constructor accepts arguments.

        Classes that inherit ``object.__init__`` or typing's
        ``_no_init_or_replace_init`` sentinel (Protocol/Generic without their
        own ``__init__``) report a ``(*args, **kwargs)`` signature on Python
        3.12+ but still reject constructor arguments.
        """
        if not inspect.isclass(factory):
            return True
        init = factory.__init__
        if init is object.__init__:
            return False
        return getattr(init, "__name__", None) != "_no_init_or_replace_init"

    @staticmethod
    def _factory_parameters(factory: Any) -> dict[str, inspect.Parameter]:
        """Return the accepted constructor parameters, excluding self/cls."""
        try:
            signature = inspect.signature(factory)
        except (TypeError, ValueError):
            return {}
        return {
            name: parameter
            for name, parameter in signature.parameters.items()
            if name not in {"self", "cls"}
        }

    def _build_dependency_kwargs(
        self, factory: Any, dependency_instances: dict[str, Any]
    ) -> dict[str, Any]:
        target = factory.__init__ if inspect.isclass(factory) else factory
        try:
            hints = get_type_hints(target)
        except Exception:  # noqa: BLE001
            hints = {}

        kwargs: dict[str, Any] = {}
        try:
            signature = inspect.signature(factory)
        except (TypeError, ValueError):
            signature = None

        if signature is None:
            return kwargs

        for parameter in signature.parameters.values():
            if parameter.name in {"settings", "self", "cls"}:
                continue
            if parameter.kind in {
                inspect.Parameter.VAR_POSITIONAL,
                inspect.Parameter.VAR_KEYWORD,
            }:
                continue

            dependency = self._match_dependency(
                parameter.name, hints.get(parameter.name), dependency_instances
            )
            if dependency is not None:
                kwargs[parameter.name] = dependency
        return kwargs

    @staticmethod
    def _match_dependency(
        name: str, hint: Any, dependency_instances: dict[str, Any]
    ) -> Any | None:
        if name in dependency_instances:
            return dependency_instances[name]

        if hint is None:
            return None

        origin = get_origin(hint)
        if origin is None:
            candidates = [hint]
        else:
            candidates = [
                candidate for candidate in get_args(hint) if candidate is not type(None)
            ]

        for candidate in candidates:
            candidate_name = getattr(candidate, "__name__", None)
            if isinstance(candidate_name, str):
                resolved = dependency_instances.get(candidate_name.lower())
                if resolved is not None:
                    return resolved
        return None

    def _select_provider_name(
        self, capability_name: str, capability: CapabilityManifest
    ) -> str:
        configured = self._settings.components.get(capability_name, {}).get("provider")
        provider_name = (
            configured if isinstance(configured, str) and configured else None
        )
        provider = self._registry.resolve_provider(capability, provider_name)
        return provider.name

    def get(self, capability: str, provider: str) -> Any:
        """Return one initialized provider instance."""
        try:
            return self._instances[(capability, provider)]
        except KeyError as exc:
            raise ApplicationError(
                f"Provider {provider!r} is not initialized for capability {capability!r}"
            ) from exc

    def clear(self) -> None:
        """Forget instances after their lifecycle stack has been closed."""
        self._instances.clear()
        self._selected_providers.clear()
        self._initializing.clear()
