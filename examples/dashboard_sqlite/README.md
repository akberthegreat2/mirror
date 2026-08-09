# Mirror Django Admin + SQLite example

This is the smallest standalone dashboard example for Mirror. It deliberately
uses **only Django Admin and SQLite**. It does not install or invoke Fetch,
HTTPX, Scrapy, Playwright, Celery, Redis, or PostgreSQL.

## Run

From the repository root, install `mirror-core` and `mirror-control-django`,
then install Django. From this directory:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open `/admin/` and log in. The Mirror control-plane models are registered in
Django Admin and use the same SQLite database configured by the example.

## What this proves

- `mirror-control-django` is a reusable Django app, not a custom dashboard UI.
- Django Admin is the dashboard surface.
- Mirror control-plane metadata can be persisted in SQLite.
- The dashboard does not require a web capability/provider to exist.
- The control plane can be tested independently from Fetch/Crawl/Scrape.

This example is intentionally separate from the distributed Celery/Redis/
PostgreSQL deployment example.
