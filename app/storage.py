import uuid

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

ALLOWED_CONTENT_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

# Magic-byte prefixes, so a renamed .txt can't pass just because the
# browser sent a convenient Content-Type header.
_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",  # WEBP is RIFF....WEBP; checked further below
}


class UploadRejected(Exception):
    pass


def _sniff_content_type(head: bytes) -> str | None:
    for magic, content_type in _MAGIC_BYTES.items():
        if head.startswith(magic):
            if content_type == "image/webp" and head[8:12] != b"WEBP":
                continue
            return content_type
    return None


def validate_upload(file_storage) -> str:
    """Validate a Flask/werkzeug FileStorage. Returns the validated
    content type, or raises UploadRejected."""
    declared_type = file_storage.mimetype
    if declared_type not in ALLOWED_CONTENT_TYPES:
        raise UploadRejected(f"unsupported content type: {declared_type}")

    head = file_storage.stream.read(12)
    file_storage.stream.seek(0)
    sniffed_type = _sniff_content_type(head)
    if sniffed_type != declared_type:
        raise UploadRejected("file contents do not match declared content type")

    file_storage.stream.seek(0, 2)  # seek to end
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise UploadRejected(f"file too large: {size} bytes (max {MAX_UPLOAD_BYTES})")

    return declared_type


def _s3_client(app):
    # No access keys here. boto3's default credential chain finds
    # credentials on its own: an AWS CLI profile locally, an EC2
    # instance profile (IAM role) in production. Same code either way.
    #
    # signature_version pinned to sigv4 explicitly: without it, boto3's
    # default for us-east-1 can silently presign with the legacy sigv2
    # scheme, which AWS has been deprecating region by region for years.
    return boto3.client(
        "s3",
        region_name=app.config["AWS_REGION"],
        config=Config(signature_version="s3v4"),
    )


def upload_post_image(app, file_storage, content_type: str) -> str:
    ext = ALLOWED_CONTENT_TYPES[content_type]
    key = f"posts/{uuid.uuid4()}.{ext}"

    s3 = _s3_client(app)
    try:
        s3.upload_fileobj(
            file_storage.stream,
            app.config["S3_BUCKET_UPLOADS"],
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except ClientError as exc:
        raise UploadRejected(f"upload to S3 failed: {exc}") from exc

    return key


def presigned_get_url(app, s3_key: str, expires_in: int = 300) -> str:
    s3 = _s3_client(app)
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": app.config["S3_BUCKET_UPLOADS"], "Key": s3_key},
        ExpiresIn=expires_in,
    )
