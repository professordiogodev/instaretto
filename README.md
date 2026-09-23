# Instaretto

Welcome! Instaretto is a small photo-sharing app built specifically to
teach one thing well: **how real apps use storage** — a relational
database for structured data, object storage for files, and a log
pipeline that doesn't blow your storage budget.

The app itself is intentionally boring: sign up, log in, post a
picture with a caption, see a feed, like things. You'll have it fully
working in a few minutes. The interesting part is what's underneath —
and the full hands-on lab walks you through every layer of it, first
on your own laptop, then for real on AWS.

**New here? Start with [LAB.md](LAB.md).** It's a step-by-step guide
written for people who haven't necessarily touched AWS before —
each part ends with a concrete checkpoint so you always know if
you're still on track.

## What you'll practice

- Running a real app + database locally with Docker
- Object storage (S3): private buckets, presigned URLs, upload
  validation
- Relational storage (PostgreSQL): schemas, foreign keys, constraints
  that do real work
- Moving from a local database to a managed one (RDS) without
  rewriting the app
- Credentials done right: no access keys anywhere in the code — local
  dev uses your AWS CLI profile, production uses an EC2 instance role
- Cost-aware logging: rotating, shipping, and tiering log files
- Provisioning cloud infrastructure by hand (console + CLI), and
  tearing it all back down afterward

No prior AWS experience required. Some comfort with the command line
and a text editor is enough — the lab explains each new concept as it
shows up.

## Stack

- Flask + SQLAlchemy, server-rendered Jinja2 templates, no JS build step
- PostgreSQL (local: a Docker container; on AWS: RDS)
- S3 for image storage, accessed via boto3's default credential chain
  (your AWS CLI profile locally, an EC2 instance role in production —
  same application code either way)
- Gunicorn in the container
- Plain SQL schema (`schema.sql`), no migration framework — it's meant
  to be read, not just run

## Repo layout

```
app/                  Flask application (routes, models, templates, S3 client)
schema.sql             Database schema + seed data (read this, don't just run it)
Dockerfile
docker-compose.yml      Local dev: app + Postgres
scripts/ship_logs.sh    Ships rotated logs to S3
aws/lifecycle.json      S3 lifecycle rule for the logs bucket
aws/iam-policy.json     Least-privilege policy for the EC2 instance role
LAB.md                 The full hands-on lab — start here
```

## Getting started

Don't set this up from this README — **[LAB.md](LAB.md) is the single
source of truth for every setup step**, from `docker compose up`
through tearing down the AWS resources at the end. Duplicating those
steps here would just give them a second place to go stale; this file
stays a map of the repo, not a second copy of the instructions.

Open [LAB.md](LAB.md) and start at Part 0.
