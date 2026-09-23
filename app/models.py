from sqlalchemy import func

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.Text, unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    posts = db.relationship("Post", backref="author", cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="user", cascade="all, delete-orphan")


class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    s3_key = db.Column(db.Text, nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    likes = db.relationship("Like", backref="post", cascade="all, delete-orphan")

    def like_count(self) -> int:
        # Deliberately a COUNT query, not a stored counter column --
        # see LAB.md for why that tradeoff is made here.
        return db.session.query(func.count(Like.user_id)).filter(
            Like.post_id == self.id
        ).scalar()

    def liked_by(self, user_id: int) -> bool:
        if user_id is None:
            return False
        return (
            db.session.query(Like)
            .filter(Like.post_id == self.id, Like.user_id == user_id)
            .first()
            is not None
        )


class Like(db.Model):
    __tablename__ = "likes"

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    post_id = db.Column(
        db.Integer, db.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
