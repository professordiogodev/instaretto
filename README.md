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
written for people who haven't necessarily touched AWS (or even run a
Python web app) before — each part ends with a concrete checkpoint so
you always know if you're still on track.

## What you'll practice

- Running a real Flask app against a real PostgreSQL database, both on
  your own machine
- Object storage (S3): private buckets, presigned URLs, upload
  validation
- Relational storage (PostgreSQL): schemas, foreign keys, constraints
  that do real work
- Moving from a database on your laptop to a managed one (RDS)
  without rewriting the app
- Credentials done right: no access keys anywhere in the code — local
  dev uses your AWS CLI profile, production uses an EC2 instance role
- Cost-aware logging: rotating, shipping, and tiering log files
- Provisioning cloud infrastructure by hand (console + CLI), and
  tearing it all back down afterward

No prior AWS experience required, and this version of the lab doesn't
use Docker or containers anywhere — everything runs directly with a
Python virtual environment and a PostgreSQL server installed on your
machine, so there's one less new tool between you and the concepts
that actually matter here. (If you already know Docker and want to see
the same app deployed with it instead, check out the `with-docker`
branch — but that's optional, later material.)

Everything here assumes a **Linux shell**: native Linux, WSL2 on
Windows, or OrbStack (or similar) on macOS — commands are plain
`apt`/`systemctl`, nothing OS-specific beyond that.

## Stack

- Flask + SQLAlchemy, server-rendered Jinja2 templates, no JS build step
- PostgreSQL (local: installed directly on your machine; on AWS: RDS)
- S3 for image storage, accessed via boto3's default credential chain
  (your AWS CLI profile locally, an EC2 instance role in production —
  same application code either way)
- Gunicorn as the production WSGI server (used on EC2 in Part 6)
- Plain SQL schema (`schema.sql`), no migration framework — it's meant
  to be read, not just run

## Repo layout

```
app/                  Flask application (routes, models, templates, S3 client)
schema.sql             Database schema + seed data (read this, don't just run it)
requirements.txt       Python dependencies
wsgi.py                App entry point (loads .env, creates the Flask app)
scripts/ship_logs.sh    Ships rotated logs to S3
aws/lifecycle.json      S3 lifecycle rule for the logs bucket
aws/iam-policy.json     Least-privilege policy for the EC2 instance role
LAB.md                 The full hands-on lab — start here
```

## Getting started

Don't set this up from this README — **[LAB.md](LAB.md) is the single
source of truth for every setup step**, from installing PostgreSQL
through tearing down the AWS resources at the end. Duplicating those
steps here would just give them a second place to go stale; this file
stays a map of the repo, not a second copy of the instructions.

Open [LAB.md](LAB.md) and start at Part 0.
