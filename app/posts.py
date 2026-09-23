from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import IntegrityError

from app.auth import login_required
from app.extensions import db
from app.models import Like, Post
from app.storage import UploadRejected, presigned_get_url, upload_post_image, validate_upload

posts_bp = Blueprint("posts", __name__)


@posts_bp.route("/")
@login_required
def feed():
    posts = db.session.query(Post).order_by(Post.created_at.desc()).all()
    posts_view = []
    for post in posts:
        try:
            image_url = presigned_get_url(current_app, post.s3_key)
        except (BotoCoreError, ClientError) as exc:
            # Before S3 buckets exist (or with a placeholder bucket name
            # still in .env), signing fails -- degrade to a broken image
            # instead of a 500. See LAB.md Part 1.
            current_app.logger.warning(
                "presign_failed post_id=%s error=%s", post.id, exc
            )
            image_url = None
        posts_view.append(
            {
                "post": post,
                "image_url": image_url,
                "like_count": post.like_count(),
                "liked_by_me": post.liked_by(g.user.id),
            }
        )
    return render_template("feed.html", posts_view=posts_view)


@posts_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    if request.method == "POST":
        file_storage = request.files.get("image")
        description = request.form.get("description", "").strip()

        if file_storage is None or file_storage.filename == "":
            flash("Please choose an image.")
            return render_template("upload.html")

        try:
            content_type = validate_upload(file_storage)
            s3_key = upload_post_image(current_app, file_storage, content_type)
        except UploadRejected as exc:
            current_app.logger.info(
                "upload_failed user_id=%s reason=%s", g.user.id, exc
            )
            flash(f"Upload rejected: {exc}")
            return render_template("upload.html")

        post = Post(user_id=g.user.id, s3_key=s3_key, description=description)
        db.session.add(post)
        db.session.commit()

        current_app.logger.info(
            "upload_success user_id=%s post_id=%s s3_key=%s", g.user.id, post.id, s3_key
        )
        return redirect(url_for("posts.feed"))

    return render_template("upload.html")


@posts_bp.route("/posts/<int:post_id>/like", methods=["POST"])
@login_required
def like(post_id):
    like_row = Like(user_id=g.user.id, post_id=post_id)
    db.session.add(like_row)
    try:
        db.session.commit()
        current_app.logger.info("like user_id=%s post_id=%s", g.user.id, post_id)
    except IntegrityError:
        # UNIQUE(user_id, post_id) already satisfied -- this user already
        # liked this post. The database is the source of truth here, not
        # an application-level check. See LAB.md Part 4.
        db.session.rollback()
        current_app.logger.info(
            "like_rejected user_id=%s post_id=%s reason=already_liked",
            g.user.id,
            post_id,
        )
    return redirect(url_for("posts.feed"))


@posts_bp.route("/posts/<int:post_id>/unlike", methods=["POST"])
@login_required
def unlike(post_id):
    db.session.query(Like).filter_by(user_id=g.user.id, post_id=post_id).delete()
    db.session.commit()
    current_app.logger.info("unlike user_id=%s post_id=%s", g.user.id, post_id)
    return redirect(url_for("posts.feed"))
