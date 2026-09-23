# Instaretto Lab: Storage and Databases

Welcome! Over the next few hours you're going to build and run a real
(if tiny) web app, then move it from your laptop onto actual AWS
infrastructure. If you've never touched AWS before, that's completely
fine — every new concept gets a plain-language explanation the first
time it shows up, and every part of this lab ends with a **Checkpoint**:
a concrete command or thing-you-should-see that tells you whether
you're on track before you move on. If a checkpoint doesn't match,
stop and fix it there rather than pushing on — everything after it
assumes it worked.

Instaretto itself is a tiny photo-sharing app: sign up, log in, upload
a picture with a description, see a feed, like/unlike posts. The app
is not the point of this lab. The point is what's underneath it:

- **PostgreSQL** for structured, relational data (users, posts, likes)
- **S3** (AWS's object storage service) for the actual image bytes,
  kept out of the database entirely
- **A log pipeline** that rotates, ships, and tiers log files with an
  eye on cost, not just "does it work"

You'll run everything locally first (Parts 1–5), then move the same
app to a real cloud server with a real managed database (Part 6),
changing as little as possible along the way — which is itself the
lesson: a well-built app shouldn't care much where its database lives.

## Part 0: Before you start

You need:

- **Docker Desktop** (or an equivalent Docker + Compose setup) —
  this runs the app and a local database in isolated containers, so
  you don't have to install Python or Postgres directly on your machine
- **AWS CLI v2**, configured with a profile that has permissions to
  create S3 buckets, an RDS database, an EC2 server, and IAM roles.
  Run `aws configure` (or `aws configure sso` if your school/org uses
  single sign-on), then confirm it worked with:

  ```
  aws sts get-caller-identity
  ```

  You should get back a small JSON blob with your account ID — if you
  get an error instead, fix that before continuing.
- **Git**, and a text editor

**Pick a short name tag once and reuse it everywhere** — your initials
or student ID, lowercase, no spaces (e.g. `dbarros`). Every AWS
resource you create in this lab gets that tag appended, e.g.
`instaretto-uploads-dbarros`. This matters most for S3: **bucket names
are globally unique across all of AWS**, not just your account, so
`instaretto-uploads` alone will almost certainly collide with someone
else's bucket somewhere in the world and your bucket creation will
fail with `BucketAlreadyExists`.

Region for this whole lab: **us-east-1** (Northern Virginia). Stick to
this region throughout — mixing regions is a common source of
confusing "it says it doesn't exist" errors.

Clone or copy this repo to your machine before continuing.

---

## Part 1: Run it locally

The app can run before any AWS resources exist at all — you just won't
be able to upload real pictures yet. That's a deliberate first
checkpoint: it proves the app and the database work together,
completely independent of anything in the cloud.

1. Copy the env file (this holds configuration and secrets the app
   reads on startup — it's deliberately gitignored so you never commit
   secrets) and generate a secret key:

   ```
   cp .env.example .env
   python3 -c "import secrets; print(secrets.token_hex(32))"
   ```

   Paste the output into `SECRET_KEY` in `.env`. Leave `DATABASE_URL` as
   the default (it points at the `db` service in docker-compose). Leave
   `S3_BUCKET_UPLOADS` / `S3_BUCKET_LOGS` as the `<yourname>` placeholders
   for now — replace `<yourname>` with your tag, even though the buckets
   don't exist yet.

2. Create the local log directory the container will write into:

   ```
   mkdir -p data/logs
   chmod 777 data/logs
   ```

   (The `chmod` is a lab shortcut so the container's non-root user can
   write into a directory owned by your host user — not something
   you'd do on a real server, where you'd match ownership properly
   instead of opening it up to everyone.)

3. Start everything:

   ```
   docker compose up --build
   ```

   This builds the app image, starts a Postgres container (loading
   `schema.sql` automatically the first time it boots — open that file
   now and skim it, it's short and worth reading before you run it
   blind), and starts the Flask app under Gunicorn. Leave this running
   in its own terminal tab.

4. Open <http://localhost:8000>. Log in as a seed user (a user already
   created for you by `schema.sql`, so you don't have to sign up first
   just to see something): `alice@example.com` / `password123`. You
   should see the feed with two seed posts — **their images will show
   as broken picture icons**, because their `s3_key` values are
   placeholders and no bucket exists yet. That's expected, and
   `schema.sql` says so in a comment too — don't spend time debugging
   it.

5. Try signing up a new account, logging out, logging back in.

**Checkpoint:** the feed loads, shows two seed posts with broken
images, and you can sign up / log in / log out. Run
`docker compose logs web` in another terminal and you should see
`login_success` lines for your activity.

---

## Part 2: Create the S3 buckets

**S3 (Simple Storage Service)** is AWS's object storage: think of a
"bucket" as a giant, infinitely-scalable folder that holds files
("objects") addressed by a key (a path-like string), not a
filesystem you mount. You need two buckets: one to hold uploaded
images, one to hold shipped log files.

Both buckets stay **fully private** the entire lab — Block Public
Access stays on, and you never attach a bucket policy or object ACL
that opens anything up to the internet. The app reaches images only
through short-lived, signed URLs it generates itself (more on that in
Part 3) — never through a public bucket.

### Console

If you'd rather click through the AWS web console than type commands:

1. Go to the S3 service → **Create bucket**.
2. Bucket name: `instaretto-uploads-<yourname>`. Region: **us-east-1**.
3. Leave **Block all public access** checked (it's the default —
   don't turn it off).
4. Leave ACLs disabled (default) and versioning off.
5. Create the bucket.
6. Repeat for `instaretto-logs-<yourname>`.

### CLI

Or, the equivalent from your terminal:

```
aws s3api create-bucket \
  --bucket instaretto-uploads-<yourname> \
  --region us-east-1

aws s3api create-bucket \
  --bucket instaretto-logs-<yourname> \
  --region us-east-1
```

(us-east-1 is the *one* region where `create-bucket` does **not** take
a `--create-bucket-configuration LocationConstraint=...` flag — every
other region needs one. A common gotcha if you ever copy this command
for a different region.)

Now update `.env` with your real bucket names (replace the
`<yourname>` placeholders in `S3_BUCKET_UPLOADS` / `S3_BUCKET_LOGS`
with the actual bucket names you just created) and restart the app so
it picks up the change:

```
docker compose up -d --force-recreate web
```

**Checkpoint:**

```
aws s3 ls | grep instaretto
aws s3api get-public-access-block --bucket instaretto-uploads-<yourname>
```

The first command should list both buckets. The second should show
all four block-public-access settings as `true`.

---

## Part 3: Upload a picture and see it in the feed

1. Log in, click **Upload**, choose a real `.jpg`/`.png`/`.webp` under
   5 MB (any picture on your laptop works), add a description, submit.
2. You should land back on the feed and see your image rendered for
   real this time.

**Checkpoint 1 — the object actually landed in S3:**

```
aws s3 ls s3://instaretto-uploads-<yourname>/posts/
```

You should see one object named `<uuid>.<ext>` — not your original
filename. The app never trusts or stores the client's filename; it
generates a random one itself.

**Checkpoint 2 — the bucket really is private.** In your browser,
right-click the uploaded image and choose "copy image address," then
paste it somewhere to look at it: it's long, and includes query
parameters like `X-Amz-Signature` and `X-Amz-Expires`. That's a
**presigned URL** — a normal S3 URL with a cryptographic signature
attached that temporarily grants read access to one specific private
object, without making the bucket or object public. Now strip
everything from the `?` onward and open *that* bare URL directly:

```
https://instaretto-uploads-<yourname>.s3.amazonaws.com/posts/<uuid>.<ext>
```

You should get `AccessDenied`. The object is *only* reachable through
a presigned URL the app generates on the fly, and that URL stops
working after 5 minutes (see `expires_in` in `presigned_get_url()` in
`app/storage.py`) — so even a leaked link goes stale on its own.

**Checkpoint 3 — validation isn't just cosmetic.** Take any text file,
rename it to `fake.jpg`, and try to upload it through the app. The
server doesn't just trust the browser's claim that this is a JPEG — it
opens the file and checks its first few bytes against the real magic
numbers JPEG/PNG/WEBP files start with. It should reject the upload
with "file contents do not match declared content type." Check
`docker compose logs web` for the `upload_failed` line to see it
happen.

---

## Part 4: Inspect the database with psql

`psql` is Postgres's interactive command-line client. Connect to the
database running in your local Postgres container:

```
docker compose exec db psql -U instaretto -d instaretto
```

Look at the schema (`\d` describes a table):

```sql
\d users
\d posts
\d likes
```

Note in `\d posts` that `s3_key` is just a `text` column — no image
bytes anywhere near this table, ever. And in `\d likes`, the primary
key is the *pair* `(user_id, post_id)` together, not a separate
synthetic `id` column — that pairing is what makes "one like per user
per post" a fact the database enforces, not just something the app
promises to check.

**Checkpoint — watch that constraint do its job.** Pick a real
`user_id` and `post_id` from your data:

```sql
SELECT id FROM users;
SELECT id FROM posts;
```

Then try inserting the same like twice:

```sql
INSERT INTO likes (user_id, post_id) VALUES (1, 1);
INSERT INTO likes (user_id, post_id) VALUES (1, 1);
```

The second insert should fail with:

```
ERROR:  duplicate key value violates unique constraint "likes_pkey"
```

That's exactly the constraint the app leans on in `app/posts.py`'s
`like()` route — it doesn't pre-check "has this user already liked
this post" in application code, it just attempts the insert and reacts
if the database rejects it. The database is the source of truth for
that rule, not the application.

Also worth trying:

```sql
SELECT p.id, p.description, count(l.user_id) AS likes
FROM posts p LEFT JOIN likes l ON l.post_id = p.id
GROUP BY p.id ORDER BY p.created_at DESC;
```

That's the same `COUNT`-based approach `Post.like_count()` uses in the
app — there's no stored counter column that could ever drift out of
sync with reality.

Type `\q` to exit `psql`.

---

## Part 5: Ship logs and apply the lifecycle rule

The app writes to `data/logs/app.log` on your host machine (this
directory is bind-mounted into the container at `/var/log/instaretto`,
so files written inside the container show up right here on your
laptop too) using a handler that rotates the log file at midnight UTC,
producing files named like `app.log.2026-09-23`. Waiting for real
midnight isn't practical mid-class, so we'll fake a rotation by
copying the active file:

```
cp data/logs/app.log "data/logs/app.log.$(date -u +%F)"
ls data/logs/
```

You should now see `app.log` (still being actively written to — leave
it alone) and one `app.log.YYYY-MM-DD` file (the "rotated" one).

Now ship it with the provided script:

```
LOG_DIR=./data/logs \
S3_BUCKET_LOGS=instaretto-logs-<yourname> \
AWS_REGION=us-east-1 \
./scripts/ship_logs.sh
```

Open `scripts/ship_logs.sh` and skim it — it gzips the rotated file,
uploads it to
`s3://instaretto-logs-<yourname>/logs/instaretto/<hostname>/YYYY/MM/DD/app.log.YYYY-MM-DD.gz`,
and deletes the local copy **only after confirming the upload
succeeded**. It never touches `app.log` itself, so it's always safe to
run even while the app keeps writing new log lines.

**Checkpoint 1:**

```
aws s3 ls s3://instaretto-logs-<yourname>/logs/instaretto/ --recursive
ls data/logs/
```

The object should show up in S3 under the dated prefix; locally, the
`app.log.YYYY-MM-DD` and `.gz` files should be gone — only `app.log`
remains.

**Checkpoint 2 — it's safe to rerun:**

```
./scripts/ship_logs.sh
```

(with the same environment variables as before). There's nothing left
to ship, so it should print "No rotated log files to ship." and exit
cleanly — it doesn't re-upload anything or error out.

### Apply the lifecycle rule

A **lifecycle rule** tells S3 to automatically move objects to
cheaper, slower storage classes as they age, and eventually delete
them — without you lifting a finger after today.

```
aws s3api put-bucket-lifecycle-configuration \
  --bucket instaretto-logs-<yourname> \
  --lifecycle-configuration file://aws/lifecycle.json \
  --region us-east-1
```

Console equivalent: open your logs bucket → **Management** tab →
**Create lifecycle rule** → apply it to objects with prefix
`logs/instaretto/` → transition to Standard-IA at 30 days, Glacier Deep
Archive at 90 days, expire (permanently delete) at 365 days — matching
what's already written in `aws/lifecycle.json`.

**Why gzip and bundle into one file per day instead of shipping (and
tiering) every individual log line or file separately?** Two S3
pricing facts make the naive approach surprisingly expensive:

- Standard-IA (and Intelligent-Tiering) **bills any object smaller
  than 128 KB as if it were 128 KB**.
- Standard-IA also has a **30-day minimum storage charge** per object,
  even if you delete it sooner.

A busy app can produce thousands of small log lines a day. Ship and
tier each one as its own tiny object and you're paying the 128 KB
minimum, thousands of times over, for objects that are actually a few
hundred bytes. Gzipping and bundling into one file per host per day
means you tier a handful of larger objects instead — so the lifecycle
transitions actually save money, instead of quietly costing more than
just leaving everything in Standard storage.

**Checkpoint:**

```
aws s3api get-bucket-lifecycle-configuration --bucket instaretto-logs-<yourname>
```

should show the rule you just applied.

If this were a real production server, you'd also want this running
automatically every day without you remembering — see the comment
block at the bottom of `scripts/ship_logs.sh` for a ready-to-use
crontab line and a systemd-timer alternative.

---

## Part 6: Move to RDS + EC2 with an IAM role

This is the biggest part of the lab — take it slowly, and don't skip
the explanations, since almost every piece here is a new AWS concept.
Grab a coffee.

Here's the whole idea in one sentence: **only `DATABASE_URL` changes.**
Everything else about the app — including how it talks to S3 — stays
exactly the same code. Locally, boto3 (AWS's Python SDK) found
credentials through your AWS CLI profile; on EC2, it'll find them
through an **instance profile** (an IAM role attached directly to the
server) instead. At no point does an access key get written into the
app, the container image, or the instance itself — the credentials are
handed to the code automatically, from a different place, without the
code knowing or caring which.

### 6.1 Create two security groups

A **security group** is a virtual firewall attached to an AWS
resource — a set of rules saying what traffic is allowed in (and out).
You need two: one for your server, one for your database.

Console: EC2 service → **Security Groups** → **Create security group**,
twice, both in your account's default VPC (a **VPC**, Virtual Private
Cloud, is an isolated network inside AWS — every account gets a
default one to start with, which is fine for this lab):

- `instaretto-ec2-sg-<yourname>` — inbound rules: SSH (port 22) from
  *My IP* only, and custom TCP port 8000 from `0.0.0.0/0` (any
  address — so you can view the app in a browser; in a real deployment
  you'd put this behind a load balancer instead of exposing it this
  openly).
- `instaretto-rds-sg-<yourname>` — inbound rule: PostgreSQL (port
  5432), with the **source set to the `instaretto-ec2-sg-<yourname>`
  security group itself**, not an IP range. This is what makes "the
  database only accepts connections from the app server" a fact
  enforced by AWS's network layer, rather than a convention you have
  to remember to uphold.

CLI:

```
VPC_ID=$(aws ec2 describe-vpcs --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text --region us-east-1)

EC2_SG_ID=$(aws ec2 create-security-group \
  --group-name instaretto-ec2-sg-<yourname> \
  --description "Instaretto app instance" \
  --vpc-id "$VPC_ID" --region us-east-1 --query GroupId --output text)

RDS_SG_ID=$(aws ec2 create-security-group \
  --group-name instaretto-rds-sg-<yourname> \
  --description "Instaretto RDS instance" \
  --vpc-id "$VPC_ID" --region us-east-1 --query GroupId --output text)

MY_IP=$(curl -s https://checkip.amazonaws.com)

aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" \
  --protocol tcp --port 22 --cidr "${MY_IP}/32" --region us-east-1

aws ec2 authorize-security-group-ingress --group-id "$EC2_SG_ID" \
  --protocol tcp --port 8000 --cidr 0.0.0.0/0 --region us-east-1

aws ec2 authorize-security-group-ingress --group-id "$RDS_SG_ID" \
  --protocol tcp --port 5432 --source-group "$EC2_SG_ID" --region us-east-1
```

Keep `$EC2_SG_ID` and `$RDS_SG_ID` around (they'll stay set in this
terminal session) — you'll use them again below.

### 6.2 Create the RDS instance

**RDS (Relational Database Service)** is AWS's managed Postgres (and
MySQL, and others) offering — AWS handles the server, patching, and
backups; you just get a connection endpoint. This is the same Postgres
you were already running in Docker, just hosted for you instead of by
you.

Console: RDS service → **Create database** → Standard create →
PostgreSQL → a recent 16.x engine version → template Dev/Test (or Free
tier if your account has it available) → DB instance identifier
`instaretto-db-<yourname>` → master username `instaretto`, set and
**save** a master password somewhere → instance class `db.t3.micro` →
storage: gp3, 20 GB → Connectivity: your default VPC, **Public access:
No** (this database should never be reachable directly from the
internet), VPC security group: choose existing →
`instaretto-rds-sg-<yourname>` (remove the default one it suggests) →
Initial database name `instaretto` → Create database.

CLI:

```
aws rds create-db-instance \
  --db-instance-identifier instaretto-db-<yourname> \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username instaretto \
  --master-user-password '<choose-a-password>' \
  --allocated-storage 20 \
  --storage-type gp3 \
  --db-name instaretto \
  --vpc-security-group-ids "$RDS_SG_ID" \
  --no-publicly-accessible \
  --region us-east-1
```

This takes several minutes to provision — a good time for a break.
Wait for it to finish:

```
aws rds wait db-instance-available \
  --db-instance-identifier instaretto-db-<yourname> --region us-east-1

aws rds describe-db-instances \
  --db-instance-identifier instaretto-db-<yourname> \
  --query 'DBInstances[0].Endpoint.Address' --output text --region us-east-1
```

Save that endpoint hostname somewhere — you'll need it for
`DATABASE_URL` shortly.

### 6.3 Create the IAM role for EC2

**IAM (Identity and Access Management)** is how AWS controls who and
what can do what. A **role** is an identity that isn't a person — here,
it'll belong to your EC2 server itself, so the server can access S3
without any human's credentials ever touching it.

The policy below (`aws/iam-policy.json`) is deliberately
**least-privilege**: it only allows `PutObject`/`GetObject` under
`posts/*` in the uploads bucket, and `PutObject` under
`logs/instaretto/*` in the logs bucket. Nothing else — no
account-wide S3 access, no wildcard bucket-level actions. If this
role's credentials ever leaked, the blast radius is exactly those two
prefixes.

First, edit `aws/iam-policy.json` and replace both `<yourname>`
placeholders with your actual bucket names.

Console: IAM service → **Roles** → **Create role** → Trusted entity:
AWS service → Use case: **EC2** → Next → **Create policy** (opens a
new tab), paste the JSON from `aws/iam-policy.json`, name it
`instaretto-s3-access-<yourname>` → back in the role wizard, attach
that policy → name the role `instaretto-ec2-role-<yourname>` → Create
role.

CLI:

```
cat > /tmp/ec2-trust-policy.json <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Service": "ec2.amazonaws.com" },
    "Action": "sts:AssumeRole"
  }]
}
EOF

aws iam create-role \
  --role-name instaretto-ec2-role-<yourname> \
  --assume-role-policy-document file:///tmp/ec2-trust-policy.json

aws iam put-role-policy \
  --role-name instaretto-ec2-role-<yourname> \
  --policy-name instaretto-s3-access \
  --policy-document file://aws/iam-policy.json

aws iam create-instance-profile \
  --instance-profile-name instaretto-ec2-role-<yourname>

aws iam add-role-to-instance-profile \
  --instance-profile-name instaretto-ec2-role-<yourname> \
  --role-name instaretto-ec2-role-<yourname>
```

(An **instance profile** is the small wrapper that actually attaches a
role to an EC2 instance — the console hides this distinction from you
by creating one automatically, but the CLI makes you do it explicitly.)

### 6.4 Launch the EC2 instance

**EC2 (Elastic Compute Cloud)** is just a virtual server — a regular
Linux machine you get SSH access to, same as any VM.

Console: EC2 service → **Launch instance** → Name
`instaretto-app-<yourname>` → AMI (Amazon Machine Image — the OS
template the server boots from): Amazon Linux 2023 → Instance type
`t3.micro` → Key pair: create or pick an existing one (you'll need the
private key file to SSH in — don't lose it) → Network settings: select
`instaretto-ec2-sg-<yourname>`, auto-assign public IP: enabled →
Advanced details → IAM instance profile:
`instaretto-ec2-role-<yourname>` → User data (a script that runs
automatically the first time the instance boots):

```bash
#!/bin/bash
dnf update -y
dnf install -y docker git postgresql15
systemctl enable --now docker
usermod -aG docker ec2-user
```

→ Launch instance.

CLI:

```
AMI_ID=$(aws ec2 describe-images --owners amazon \
  --filters "Name=name,Values=al2023-ami-2023.*-x86_64" \
  --query 'Images | sort_by(@,&CreationDate) | [-1].ImageId' \
  --output text --region us-east-1)

# Some accounts (school/org-managed AWS accounts in particular) have a
# default VPC whose subnets aren't flagged "default for AZ" -- when
# that's the case, run-instances can't auto-pick one and fails with
# "No subnets found for the default VPC". Pick one explicitly to avoid
# depending on that flag either way.
SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" \
  --query 'Subnets[0].SubnetId' --output text --region us-east-1)

aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type t3.micro \
  --key-name <your-key-pair-name> \
  --security-group-ids "$EC2_SG_ID" \
  --subnet-id "$SUBNET_ID" \
  --associate-public-ip-address \
  --iam-instance-profile Name=instaretto-ec2-role-<yourname> \
  --user-data file:///path/to/the/user-data/script/above.sh \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=instaretto-app-<yourname>}]' \
  --region us-east-1
```

### 6.5 Deploy the app on EC2

Get the instance's public IP address (console, or):

```
aws ec2 describe-instances --filters Name=tag:Name,Values=instaretto-app-<yourname> \
  --query 'Reservations[0].Instances[0].PublicIpAddress' --output text --region us-east-1
```

and SSH in:

```
ssh -i /path/to/your-key.pem ec2-user@<public-ip>
```

(If this hangs, give the instance another minute or two to finish
booting, and double check your security group allows SSH from your
current IP.)

Once you're in, on the instance:

```bash
git clone <this-repo-url> instaretto
cd instaretto

cat > .env <<EOF
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
DATABASE_URL=postgresql://instaretto:<the-master-password>@<rds-endpoint>:5432/instaretto
S3_BUCKET_UPLOADS=instaretto-uploads-<yourname>
S3_BUCKET_LOGS=instaretto-logs-<yourname>
AWS_REGION=us-east-1
LOG_DIR=/var/log/instaretto
EOF

# Load the schema once, directly against RDS.
psql "$(grep DATABASE_URL .env | cut -d= -f2-)" -f schema.sql

docker build -t instaretto .
sudo mkdir -p /var/log/instaretto
# Same lab shortcut as Part 1: a fresh host directory is root-owned, but
# the container runs as a non-root user, so it can't write app.log here
# without this. (docker-compose's bind mount only avoided this because
# Docker Desktop's VM doesn't enforce host UID/GID on bind mounts the
# way native Linux -- what EC2 actually runs -- does.)
sudo chmod 777 /var/log/instaretto
docker run -d --name instaretto \
  --env-file .env \
  -p 8000:8000 \
  -v /var/log/instaretto:/var/log/instaretto \
  instaretto
```

Notice what's **not** here: no `~/.aws` mount, no access key, no
secret key, anywhere in `.env` or the `docker run` command. boto3
inside the container still resolves credentials automatically — this
time from the instance metadata service, because of the instance
profile you attached in 6.3. Same application code, different
credential source, zero code changes.

**Checkpoint 1 — same code, different credential source:**

```bash
# On the EC2 instance, outside the container:
aws configure list        # shows no access key configured
aws sts get-caller-identity   # still returns an identity -- via the instance role
```

**Checkpoint 2 — the app works end to end:** from your own laptop
(not the EC2 instance), open `http://<public-ip>:8000` in a browser,
log in, upload a picture. It should behave identically to Part 3, but
the database is now RDS and the container has no AWS credentials of
its own.

**Checkpoint 3 — RDS really is locked down:** from your own laptop
(not the EC2 instance), try:

```
psql "postgresql://instaretto:<password>@<rds-endpoint>:5432/instaretto" -c "select 1;"
```

(No `psql` installed locally? `nc -zv -w 5 <rds-endpoint> 5432` shows
the same thing without needing a Postgres client.)

It should hang or time out — your laptop isn't in
`instaretto-rds-sg-<yourname>`'s allow list. Run the exact same command
from the EC2 instance instead and it should work immediately.

If you want the full picture, set up `scripts/ship_logs.sh` on a cron
job on the EC2 instance too (see the comment block at the bottom of
the script) — it'll use the same instance-profile credentials, with no
extra configuration needed on the server.

---

## Part 7: Cleanup

**Don't skip this** — everything you created in Part 6 costs money
while it's running. Order matters below: some resources refuse to
delete while something else still references them.

```bash
# 1. Terminate the EC2 instance
aws ec2 terminate-instances --instance-ids <instance-id> --region us-east-1

# 2. Delete the RDS instance (lab-only shortcut: skipping the final
#    snapshot -- in a real environment you'd usually want one)
aws rds delete-db-instance \
  --db-instance-identifier instaretto-db-<yourname> \
  --skip-final-snapshot --region us-east-1

# 3. Empty and delete both S3 buckets (a bucket must be empty before
#    AWS will let you delete it)
aws s3 rm s3://instaretto-uploads-<yourname> --recursive
aws s3api delete-bucket --bucket instaretto-uploads-<yourname> --region us-east-1

aws s3 rm s3://instaretto-logs-<yourname> --recursive
aws s3api delete-bucket --bucket instaretto-logs-<yourname> --region us-east-1

# 4. Delete the RDS security group first -- it's the one with a rule
#    that *references* the EC2 security group, so nothing points at
#    it and it can go first. The EC2 security group can't be deleted
#    until nothing references it anymore.
aws ec2 delete-security-group --group-id "$RDS_SG_ID" --region us-east-1
aws ec2 delete-security-group --group-id "$EC2_SG_ID" --region us-east-1

# 5. Detach the policy, remove the role from its instance profile, then
#    delete the profile and the role
aws iam delete-role-policy \
  --role-name instaretto-ec2-role-<yourname> --policy-name instaretto-s3-access
aws iam remove-role-from-instance-profile \
  --instance-profile-name instaretto-ec2-role-<yourname> \
  --role-name instaretto-ec2-role-<yourname>
aws iam delete-instance-profile --instance-profile-name instaretto-ec2-role-<yourname>
aws iam delete-role --role-name instaretto-ec2-role-<yourname>
```

Also stop your local containers and remove the local Postgres volume
if you're done for good: `docker compose down -v`.

**Checkpoint** — each of these should come back empty (or show
`terminated`):

```
aws s3 ls | grep instaretto
aws rds describe-db-instances --query 'DBInstances[?DBInstanceIdentifier==`instaretto-db-<yourname>`]'
aws ec2 describe-instances --filters Name=tag:Name,Values=instaretto-app-<yourname> \
  --query 'Reservations[].Instances[].State.Name'
aws iam list-roles --query 'Roles[?RoleName==`instaretto-ec2-role-<yourname>`]'
```

---

## Discussion questions

No wrong answers here — these are meant to be argued about out loud
with whoever's sitting next to you.

1. Images went into S3 as objects, users/posts/likes went into
   Postgres as rows. What would actually go wrong, mechanically, if
   you stored image bytes as a column in the `posts` table instead?
   Think about backups, replication, and what a `SELECT *` starts
   doing to your database connection.
2. Block storage (like the EBS volume backing RDS under the hood),
   object storage (S3), and relational storage (the tables Postgres
   exposes on top of that block storage) all showed up in this lab.
   Where does each one actually live in the stack, and what unit of
   access does each one give you: a byte range, a whole object, or a
   row?
3. The like count is computed with `COUNT(*)` at read time instead of
   being kept in a counter column that's incremented/decremented on
   every like/unlike. What did that choice save you from having to get
   right? Under what load would you reconsider it?
4. The `likes` table enforces "one like per user per post" with a
   composite primary key, and the app just tries the insert and reacts
   to the database's rejection. What's the alternative (check-then-insert
   in application code), and what can go wrong with it that the
   constraint-based approach can't?
5. Presigned URLs expire after 5 minutes. What's the actual attack or
   failure mode that expiration defends against, given the bucket is
   already private with no public policy?
6. Why gzip and batch log files into one-per-host-per-day objects
   before they ever touch a storage class with tiering, instead of
   just turning on Intelligent-Tiering and shipping every log line as
   it's written?
7. The EC2 instance never has AWS access keys anywhere — not in
   `.env`, not in the image, not in a mounted file. Where do the
   credentials boto3 uses actually come from, and what would you have
   to do to steal them if you had shell access to the instance versus
   if you only had read access to this git repo?
