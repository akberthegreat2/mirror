"""Provider saturation reporting for the extension registry.

Saturation is the ADR-0046 beta-gate rule: each flagship capability must have at
least ``threshold`` swappable providers. This module introspects the live
``mirror.providers`` entry points (via :func:`discover_extensions`) and reports,
per capability, the provider names and whether the flagship threshold is met.

The report reflects the installed registry. Reference providers that are retired
from the shipped catalog by ADR-0051 are removed from the registry itself; the
caller can also pass ``exclude`` to filter provider names that should not count
toward saturation (for example the reference providers pending retirement).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from mirror_core.extensions.discovery import discover_extensions
from mirror_core.extensions.models import ProviderManifest

FLAGSHIP_CAPABILITIES: tuple[str, ...] = (
    "fetch",
    "crawl",
    "embedding",
    "vectorstore",
    "retrieval",
    "search",
)
SATURATION_THRESHOLD = 3


@dataclass(frozen=True)
class CapabilitySaturation:
    """Provider inventory for a single capability."""

    capability: str
    providers: tuple[str, ...] = ()
    flagship: bool = False

    @property
    def count(self) -> int:
        return len(self.providers)

    @property
    def saturated(self) -> bool:
        return self.count >= SATURATION_THRESHOLD

    @property
    def verdict(self) -> str:
        if not self.flagship:
            return "not-flagship"
        return "saturated" if self.saturated else "not-yet-saturated"


@dataclass(frozen=True)
class SaturationReport:
    """Full saturation picture of the installed provider registry."""

    by_capability: tuple[CapabilitySaturation, ...] = field(default_factory=tuple)

    def for_capability(self, capability: str) -> CapabilitySaturation | None:
        for entry in self.by_capability:
            if entry.capability == capability:
                return entry
        return None

    @property
    def flagship(self) -> tuple[CapabilitySaturation, ...]:
        return tuple(entry for entry in self.by_capability if entry.flagship)

    @property
    def saturated_capabilities(self) -> tuple[str, ...]:
        return tuple(
            entry.capability for entry in self.by_capability if entry.saturated
        )


def provider_saturation(
    *,
    flagships: tuple[str, ...] = FLAGSHIP_CAPABILITIES,
    threshold: int = SATURATION_THRESHOLD,
    exclude: set[str] | None = None,
    manifests: list[ProviderManifest] | None = None,
) -> SaturationReport:
    """Report provider counts per capability from the installed registry.

    Args:
        flagships: Capabilities subject to the saturation rule.
        threshold: Minimum provider count for a capability to be saturated.
        exclude: Provider names that never count toward saturation.
        manifests: Optional explicit provider manifests; when omitted, the live
            ``mirror.providers`` entry points are discovered.

    Returns:
        A SaturationReport keyed by capability.
    """
    excluded = exclude or set()
    if manifests is None:
        discovered, _errors = discover_extensions(["mirror.providers"])
        manifests = [
            manifest
            for manifest in discovered
            if isinstance(manifest, ProviderManifest)
        ]

    providers_by_capability: dict[str, list[str]] = {}
    for manifest in manifests:
        if manifest.name in excluded:
            continue
        providers_by_capability.setdefault(manifest.capability, []).append(
            manifest.name
        )

    # Every flagship capability is reported even when it has zero eligible
    # providers, so the gate cannot silently miss a capability that is bare.
    reported: set[str] = set(flagships)
    reported.update(providers_by_capability)
    entries: list[CapabilitySaturation] = []
    for capability in sorted(reported):
        entries.append(
            CapabilitySaturation(
                capability=capability,
                providers=tuple(sorted(providers_by_capability.get(capability, ()))),
                flagship=capability in flagships,
            )
        )
    return SaturationReport(by_capability=tuple(entries))


__all__ = [
    "FLAGSHIP_CAPABILITIES",
    "SATURATION_THRESHOLD",
    "CapabilitySaturation",
    "SaturationReport",
    "provider_saturation",
]
