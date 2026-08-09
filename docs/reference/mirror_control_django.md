# mirror-control-django

`mirror-control-django` is Mirror's reusable Django control-plane app. It
keeps Mirror Core free of Django while exposing the control-plane metadata that
operators need to inspect and edit.

## What it ships

- a pure-Python control-plane manifest for discovery and interface projection;
- Django models for projects, pipelines, versions, runs, steps, workers,
  schedules, crawled URLs, archives, checkpoints, and dead letters;
- Django admin registrations for the control-plane models;
- a blob-backed pipeline repository for code-defined and managed pipelines;
- Django Admin registrations for the operator interface;
- a settings-friendly app boundary that can be embedded in an existing Django
  project or mounted by a generated project scaffold.

## Control-plane contract

The control plane stores pipeline definitions as versioned blobs. The database
stores metadata and indexes; the blob store stores the actual pipeline
document. Code-defined pipelines are registered as read-only records until the
user explicitly materializes them into managed pipelines.

## Primary objects

- Project
- Pipeline
- PipelineVersion
- ExecutionRun
- ExecutionStep
- Worker
- Schedule
- CrawledURL
- ArchiveRecord
- Checkpoint
- DeadLetter

## How to use it

Install the package into a Django project and add `mirror_control_django` to
`INSTALLED_APPS`. Then run migrations and open the host project's normal Django Admin URL. Mirror does not ship a competing custom dashboard view.

The package is intentionally compatible with an existing Django project and does
not require Mirror Core to import Django.
