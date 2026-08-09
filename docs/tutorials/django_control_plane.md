# Connect Mirror to Django Admin

Mirror's control plane is a reusable Django app. **Django Admin is the
operator interface; Mirror does not replace it with a parallel custom dashboard
view.

## What you get

- Django Admin for projects, pipelines, versions, runs, steps, workers,
  schedules, crawled URLs, archives, checkpoints, and dead letters;
- SQLite or another Django-supported database selected by the host project;
- blob-backed pipeline definitions and immutable versions;
- read-only handling for code-defined pipelines;
- managed pipelines that can be edited and versioned;
- a manifest catalog shared by the control-plane interfaces.

## Minimal setup

1. Install Django and `mirror-control-django`.
2. Add `mirror_control_django` to `INSTALLED_APPS`.
3. Configure the host project's `DATABASES` for the database that should own
   Mirror's control-plane metadata.
4. Run `python manage.py migrate`.
5. Add the normal Django Admin URL to the host project:

   ```python
   path("admin/", admin.site.urls)
   ```

6. Create a superuser and open `/admin/`.

The repository includes `examples/dashboard_sqlite/` as a complete standalone
example. It deliberately does not install Fetch, Crawl, HTTPX, Scrapy,
Playwright, Celery, Redis, or PostgreSQL.

## Pipeline lifecycle

- code-defined pipelines can be recorded as read-only records;
- the control plane stores a blob snapshot for inspection;
- a user can materialize a managed pipeline from that snapshot;
- managed pipelines can be edited and versioned;
- each version points at an immutable blob document.

## What Mirror still owns

Mirror Core owns pipeline compilation, planning, execution semantics,
scheduling, workers, retries, cancellation, and recovery. Django owns the
human-facing control plane and its database models; it does not become a
second execution engine.
