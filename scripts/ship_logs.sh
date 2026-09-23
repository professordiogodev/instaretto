#!/usr/bin/env bash
#
# Ships rotated Instaretto log files to S3, gzipped, under a
# date-partitioned key. Safe to rerun: a file is deleted locally only
# after its upload succeeds, and once gone it won't be shipped again.
#
# Usage: LOG_DIR=/var/log/instaretto S3_BUCKET_LOGS=instaretto-logs-<yourname> ./ship_logs.sh
#
set -euo pipefail

LOG_DIR="${LOG_DIR:?LOG_DIR must be set}"
S3_BUCKET_LOGS="${S3_BUCKET_LOGS:?S3_BUCKET_LOGS must be set}"
AWS_REGION="${AWS_REGION:-us-east-1}"
HOSTNAME_TAG="$(hostname -s)"

echo "Shipping rotated logs from ${LOG_DIR} to s3://${S3_BUCKET_LOGS}/logs/instaretto/${HOSTNAME_TAG}/"

shipped_count=0

# Rotated files look like app.log.YYYY-MM-DD (TimedRotatingFileHandler
# suffix). The active file is plain "app.log" -- excluded by this glob
# because it requires a trailing ".YYYY-MM-DD" after "app.log".
shopt -s nullglob
for logfile in "${LOG_DIR}"/app.log.[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]; do
    date_suffix="${logfile##*app.log.}"
    year="${date_suffix%%-*}"
    rest="${date_suffix#*-}"
    month="${rest%%-*}"
    day="${rest#*-}"

    gz_path="${logfile}.gz"
    gzip -f "$logfile"  # produces ${logfile}.gz, removes the plain file

    s3_key="logs/instaretto/${HOSTNAME_TAG}/${year}/${month}/${day}/app.log.${date_suffix}.gz"

    if aws s3 cp "$gz_path" "s3://${S3_BUCKET_LOGS}/${s3_key}" --region "$AWS_REGION"; then
        rm -f "$gz_path"
        echo "  shipped ${date_suffix} -> s3://${S3_BUCKET_LOGS}/${s3_key}"
        shipped_count=$((shipped_count + 1))
    else
        echo "  FAILED to upload ${gz_path} -- left in place for retry" >&2
        exit 1
    fi
done

if [ "$shipped_count" -eq 0 ]; then
    echo "No rotated log files to ship."
fi

echo "Done. Shipped ${shipped_count} file(s)."

# --- Scheduling ---------------------------------------------------------
# Crontab (daily at 01:00, after the midnight rotation has had time to
# land on disk):
#
#   0 1 * * * LOG_DIR=/var/log/instaretto S3_BUCKET_LOGS=instaretto-logs-<yourname> /path/to/scripts/ship_logs.sh >> /var/log/instaretto-shipper.log 2>&1
#
# systemd timer (alternative to cron): create a oneshot service that runs
# this script and a matching .timer unit with OnCalendar=daily, then
# `systemctl enable --now ship-logs.timer`. Preferred on systems that
# already manage everything else via systemd, since you get `journalctl`
# and `systemctl status` for free instead of grepping a redirected log file.
