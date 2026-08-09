# PR notes

This directory contains the frozen implementation notes for the major delivery
phases. Each note explains what changed, why it changed, and what was deferred.

- `PR_CORE_HARDENING_PHASE_1.md`
- `PR_CORE_ALPHA_RUNTIME.md`
- `PR_CORE_PHASE_2_PROVIDER_SWAP.md`
- `PR_CORE_PHASE_3_DX.md`
- `PR_CORE_PHASE_3_DJANGO_CONTROL_PLANE.md`
- `PR_CORE_PHASE_4_BETA_RUNTIME.md`
- `PR_CAPABILITY_BOUNDARIES.md`
- `PR_DOCS_ECOSYSTEM_AND_OPEN_SOURCE_POLICY.md`
- `PR_CORE_PHASE_5_EXTENSION_MIGRATION.md`
- `PR_DISTRIBUTED_WORKERS.md`
- `PR_CORE_PHASE_5_ECOSYSTEM_EXPANSION.md`
- `PR_CORE_PHASE_5_EXTENSION_UNIFICATION.md`
- `PR_CORE_PHASE_5_BETA_GAUNTLET.md`
- `PR_CORE_PHASE_D_BETA_CERTIFICATION.md`

## Beta structural phase

The beta release plan reworks the control plane into an independent swappable
database backend, a framework-neutral interface layer, and a Django adapter, then
saturates the provider ecosystem and hardens the remaining review findings.

- `PR_BETA_DB_BACKEND.md` — independent swappable database backend (ADR-0042)
- `PR_BETA_INTERFACE_LAYER.md` — framework-neutral interface layer (ADR-0043)
- `PR_BETA_DJANGO_ADAPTER.md` — Django as a thin adapter (ADR-0044)
- `PR_BETA_CONTROL_OPS_AND_SECURITY.md` — control-plane operations and security
  contract (ADR-0045)
- `PR_BETA_PROVIDER_SATURATION.md` — provider saturation and industry-grade
  backend policy (ADR-0046)
- `PR_BETA_RAG_ECOSYSTEM.md` — knowledge/RAG ecosystem saturation (ADR-0047)
- `PR_BETA_REFERENCE_RETIREMENT.md` — reference provider retirement and
  industry-grade replacement (ADR-0051)
- `PR_BETA_DISTRIBUTED_RECOVERY.md` — distributed recovery and worker result
  semantics (ADR-0048)
- `PR_BETA_RELEASE_GATE.md` — beta release gate and remaining hardening
  (ADR-0049, ADR-0050)
