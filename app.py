from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
import secrets

from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests
from sqlalchemy import func
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_cors import CORS
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv
import os
from google import genai
import json
import requests
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont, ImageOps
from urllib.parse import quote_plus
import random
from google.oauth2 import service_account 
from googleapiclient.discovery import build
import secrets
import hashlib
import smtplib
from email.message import EmailMessage

app = Flask(__name__)
load_dotenv()


cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
      secure=True
)

GOOGLE_WEB_CLIENT_ID = os.getenv("GOOGLE_WEB_CLIENT_ID")
ANDROID_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID_ANDROID")
CORS(app)

# =========================
# DATABASE CONNECTION
# =========================

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=10)

jwt = JWTManager(app)

# =========================
# GOOGLE GEMINI CONFIGURATION
# =========================
ai_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)
# =========================
# 1. USERS
# =========================

class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        nullable=False
    )

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(20),
        default="user"
    )

    status = db.Column(
        db.String(20),
        default="active"
    )

#google account
class GoogleAccount(db.Model):
    __tablename__ = "google_accounts"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        unique=True,
        index=True
    )

    google_sub = db.Column(
        db.String(255),
        nullable=False,
        unique=True,
        index=True
    )

    email = db.Column(
        db.String(120),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
# =========================================================
# PASSWORD RESET CODE MODEL
# =========================================================

class PasswordResetCode(db.Model):
    __tablename__ = "password_reset_codes"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    code_hash = db.Column(
        db.String(64),
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    used = db.Column(
        db.Boolean,
        default=False,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    
# =========================
# 2. BUSINESS PROFILES
# =========================

class BusinessProfile(db.Model):
    __tablename__ = "business_profiles"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    business_name = db.Column(
        db.String(150),
        nullable=False
    )

    category = db.Column(
        db.String(100)
    )

    logo_url = db.Column(
        db.String(500)
    )

    phone = db.Column(
        db.String(30)
    )

    address = db.Column(
        db.String(255)
    )

    website = db.Column(
        db.String(255)
    )

    social_media_handles = db.Column(
        db.Text
    )

    description = db.Column(
        db.Text
    )


# =========================
# 3. BRAND KITS
# =========================

class BrandKit(db.Model):
    __tablename__ = "brand_kits"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    business_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("business_profiles.id"),
        nullable=False
    )

    logo_url = db.Column(
        db.String(500)
    )

    brand_colors = db.Column(
        db.String(255)
    )

    preferred_font = db.Column(
        db.String(100)
    )

    business_name = db.Column(
        db.String(150)
    )

    contact_info = db.Column(
        db.String(255)
    )


# =========================
# 4. CATEGORIES
# =========================

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    description = db.Column(
        db.Text
    )

    is_active = db.Column(
        db.Boolean,
        default=True
    )


# =========================
# 5. TEMPLATES
# =========================

class Template(db.Model):
    __tablename__ = "templates"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=True
    )

    name = db.Column(
        db.String(150),
        nullable=False
    )

    preview_url = db.Column(
        db.String(500)
    )

    template_data = db.Column(
        db.Text
    )

    is_premium = db.Column(
        db.Boolean,
        default=False
    )

    is_active = db.Column(
        db.Boolean,
        default=True
    )


# =========================
# 6. TEMPLATE FAVORITES
# =========================

class TemplateFavorite(db.Model):
    __tablename__ = "template_favorites"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    template_id = db.Column(
        db.Integer,
        db.ForeignKey("templates.id"),
        nullable=False
    )


# =========================
# 7. PROJECTS
# =========================

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    business_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("business_profiles.id"),
        nullable=True
    )

    template_id = db.Column(
        db.Integer,
        db.ForeignKey("templates.id"),
        nullable=True
    )

    title = db.Column(
        db.String(200),
        nullable=False
    )

    content_type = db.Column(
        db.String(50)
    )

    platform = db.Column(
        db.String(50)
    )

    language = db.Column(
        db.String(50)
    )

    tone = db.Column(
        db.String(50)
    )

    design_data = db.Column(
        db.Text
    )

    status = db.Column(
        db.String(30),
        default="saved"
    )


# =========================
# 8. POSTS / POST HISTORY
# =========================

class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    project_id = db.Column(
        db.Integer,
        db.ForeignKey("projects.id"),
        nullable=True
    )

    headline = db.Column(
        db.Text
    )

    caption = db.Column(
        db.Text
    )

    promotional_text = db.Column(
        db.Text
    )

    hashtags = db.Column(
        db.Text
    )

    call_to_action = db.Column(
        db.Text
    )

    # Reel / Short Video content
    reel_idea = db.Column(
        db.Text
    )

    reel_script = db.Column(
        db.Text
    )

    language = db.Column(
        db.String(50)
    )

    content_type = db.Column(
        db.String(50)
    )

    platform = db.Column(
        db.String(50)
    )

    # Product image uploaded by user
    product_image_url = db.Column(
        db.String(500)
    )

    # Final/generated post image
    image_url = db.Column(
        db.String(500)
    )

    download_url = db.Column(
        db.String(500)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )


# =========================
# 9. SUBSCRIPTION PLANS
# =========================

class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plans"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    name = db.Column(
        db.String(50),
        unique=True,
        nullable=False
    )

    ai_generation_limit = db.Column(
        db.Integer
    )

    premium_templates = db.Column(
        db.Boolean,
        default=False
    )

    advertisements = db.Column(
        db.Boolean,
        default=True
    )

    hd_downloads = db.Column(
        db.Boolean,
        default=False
    )

    brand_kit_access = db.Column(
        db.Boolean,
        default=False
    )

    multiple_business_profiles = db.Column(
        db.Boolean,
        default=False
    )

    multiple_brand_kits = db.Column(
        db.Boolean,
        default=False
    )

    advanced_ai_options = db.Column(
        db.Boolean,
        default=False
    )

    advanced_marketing_tools = db.Column(
        db.Boolean,
        default=False
    )

    watermark = db.Column(
        db.Boolean,
        default=True
    )

    price = db.Column(
        db.Float,
        default=0.0
    )


# =========================
# 10. SUBSCRIPTIONS
# =========================

class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("subscription_plans.id"),
        nullable=False
    )

    status = db.Column(
        db.String(30),
        default="active"
    )

    start_date = db.Column(
        db.DateTime
    )

    end_date = db.Column(
        db.DateTime
    )

    google_purchase_token = db.Column(
        db.String(500)
    )


# =========================
# 11. AI USAGE
# =========================

class AIUsage(db.Model):
    __tablename__ = "ai_usage"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    generation_type = db.Column(
        db.String(50)
    )

    generation_count = db.Column(
        db.Integer,
        default=1
    )

    usage_date = db.Column(
        db.Date
    )


# =========================
# 12. REPORTS
# =========================

class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True
    )

    report_type = db.Column(
        db.String(50)
    )

    reason = db.Column(
        db.Text
    )

    status = db.Column(
        db.String(30),
        default="pending"
    )


# =========================
# 13. DAILY CONTENT IDEAS
# =========================

class DailyContentIdea(db.Model):
    __tablename__ = "daily_content_ideas"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    business_profile_id = db.Column(
        db.Integer,
        db.ForeignKey("business_profiles.id"),
        nullable=True
    )

    idea = db.Column(
        db.Text,
        nullable=False
    )

    content_type = db.Column(
        db.String(50)
    )

    language = db.Column(
        db.String(50)
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )
    usage_date = db.Column(
    db.Date,
    nullable=False
)
    platform = db.Column(db.String(50))      # e.g., 'youtube', 'instagram', 'facebook'
    target_url = db.Column(db.Text)          # Asli video/content ka link
 # =========================================================
# AI USAGE ROUTE (Single Source of Truth)
# =========================================================

@app.route("/api/ai-usage", methods=["GET"])
@jwt_required()
def get_ai_usage():
    try:
        user_id = int(get_jwt_identity())

        # Ab yeh database se plan ki real limit (jaise 50) aur usage uthaye ga
        usage_status = check_ai_generation_limit(user_id)

        used = usage_status["used"]
        limit = usage_status["limit"]
        remaining = usage_status["remaining"]
        plan_name = usage_status["plan"]

        percentage = used / limit if limit > 0 else 0
        if percentage > 1:
            percentage = 1

        return jsonify({
            "success": True,
            "used": used,
            "limit": limit,
            "remaining": remaining,
            "percentage": percentage,
            "plan": plan_name
        }), 200

    except Exception as e:
        print("AI Usage Error:", str(e))
        return jsonify({
            "success": False,
            "message": "Unable to load AI usage"
        }), 500

 # =========================================================
# CHECK USER PREMIUM TEMPLATE ACCESS
# =========================================================

def user_has_premium_templates(user_id):

    subscription = (
        Subscription.query
        .filter_by(user_id=user_id)
        .order_by(
            Subscription.id.desc()
        )
        .first()
    )

    if not subscription:
        return False

    if subscription.status != "active":
        return False

    if (
        subscription.end_date
        and subscription.end_date < datetime.utcnow()
    ):
        return False

    plan = SubscriptionPlan.query.get(
        subscription.plan_id
    )

    if not plan:
        return False

    return bool(
        plan.premium_templates
    )
# =========================
# DATABASE TABLE CREATION
# =========================
with app.app_context():
    db.create_all()

# =========================================================
# UNIFIED LOGIN API (FOR BOTH USERS & ADMINS)
# =========================================================

@app.route("/api/login", methods=["POST"])
def login():
    try:
        data = request.get_json() or {}

        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""

        # Validation
        if not email or not password:
            return jsonify({
                "success": False,
                "message": "Email and password are required"
            }), 400

        # Find User
        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        # Password Check
        if not check_password_hash(user.password_hash, password):
            return jsonify({
                "success": False,
                "message": "Invalid email or password"
            }), 401

        # Status Check (Active / Blocked / Inactive)
        if user.status != "active":
            return jsonify({
                "success": False,
                "message": "Your account is not active"
            }), 403

        # Create JWT Token
        access_token = create_access_token(
            identity=str(user.id)
        )

        return jsonify({
            "success": True,
            "message": "Login successful",
            "token": access_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,      # <--- Yeh 'admin' ya 'user' batayega
                "status": user.status
            }
        }), 200

    except Exception as e:
        print("LOGIN ERROR:", str(e))
        return jsonify({
            "success": False,
            "message": "Login failed due to server error"
        }), 500
#sign up 
@app.route("/api/register", methods=["POST"])
def register():

    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")

    if not name or not email or not password:
        return jsonify({
            "success": False,
            "message": "Name, email and password are required"
        }), 400

    existing_user = User.query.filter_by(email=email).first()

    if existing_user:
        return jsonify({
            "success": False,
            "message": "Email already registered"
        }), 409

    password_hash = generate_password_hash(password)

    new_user = User(
        name=name,
        email=email,
        password_hash=password_hash,
        role="user",
        status="active"
    )

    db.session.add(new_user)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "Registration successful"
    }), 201

#google login
@app.route("/api/auth/google", methods=["POST"])
def google_login():
    try:
        data = request.get_json(silent=True) or {}

        google_token = data.get("id_token")

        if not google_token:
            return jsonify({
                "success": False,
                "message": "Google ID token is required"
            }), 400

        google_client_id = os.getenv("GOOGLE_WEB_CLIENT_ID")

        if not google_client_id:
            return jsonify({
                "success": False,
                "message": "Google login is not configured on the server"
            }), 500

        # Verify Google ID token
        try:
            id_info = google_id_token.verify_oauth2_token(
                google_token,
                google_auth_requests.Request(),
                google_client_id
            )
        except Exception as e:
            print("Google token verification error:", e)

            return jsonify({
                "success": False,
                "message": "Invalid Google ID token"
            }), 401

        # Verify issuer
        issuer = id_info.get("iss")

        if issuer not in (
            "accounts.google.com",
            "https://accounts.google.com"
        ):
            return jsonify({
                "success": False,
                "message": "Invalid Google token issuer"
            }), 401

        google_sub = id_info.get("sub")
        email = id_info.get("email")
        email_verified = id_info.get("email_verified", False)
        name = id_info.get("name") or (
            email.split("@")[0] if email else "Google User"
        )

        if not google_sub:
            return jsonify({
                "success": False,
                "message": "Google account ID is missing"
            }), 401

        if not email:
            return jsonify({
                "success": False,
                "message": "Google account email is missing"
            }), 401

        if not email_verified:
            return jsonify({
                "success": False,
                "message": "Google email is not verified"
            }), 403

        # ---------------------------------------------------------
        # 1. Check whether this Google account already exists
        # ---------------------------------------------------------

        google_account = GoogleAccount.query.filter_by(
            google_sub=google_sub
        ).first()

        user = None

        if google_account:
            user = User.query.get(google_account.user_id)

            if not user:
                db.session.delete(google_account)
                db.session.commit()

                google_account = None

        # ---------------------------------------------------------
        # 2. If Google account is not linked, check email
        # ---------------------------------------------------------

        if not google_account:

            user = User.query.filter_by(
                email=email
            ).first()

            if user:

                # Existing admin accounts must continue using
                # normal email/password login.
                if user.role == "admin":
                    return jsonify({
                        "success": False,
                        "message": "Admin accounts must use email and password login."
                    }), 403

                google_account = GoogleAccount(
                    user_id=user.id,
                    google_sub=google_sub,
                    email=email
                )

                db.session.add(google_account)

            else:

                # -------------------------------------------------
                # 3. Create new normal user
                # -------------------------------------------------

                random_password = secrets.token_urlsafe(32)

                user = User(
                    name=name,
                    email=email,
                    password_hash=generate_password_hash(
                        random_password
                    ),
                    role="user",
                    status="active"
                )

                db.session.add(user)
                db.session.flush()

                google_account = GoogleAccount(
                    user_id=user.id,
                    google_sub=google_sub,
                    email=email
                )

                db.session.add(google_account)

        # ---------------------------------------------------------
        # 4. Check account status
        # ---------------------------------------------------------

        if user.status != "active":

            db.session.rollback()

            return jsonify({
                "success": False,
                "message": "Your account is not active."
            }), 403

        db.session.commit()

        # ---------------------------------------------------------
        # 5. Create YOUR application's JWT
        # ---------------------------------------------------------

        access_token = create_access_token(
            identity=str(user.id)
        )

        return jsonify({
            "success": True,
            "message": "Google login successful",
            "token": access_token,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "status": user.status
            }
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Google login error:", e)

        return jsonify({
            "success": False,
            "message": "Google login failed",
            "error": str(e)
        }), 500

# =========================================================
# PASSWORD RESET EMAIL HELPER
# =========================================================

def send_password_reset_email(receiver_email, code):

    smtp_host = os.getenv(
        "SMTP_HOST",
        "smtp.gmail.com"
    )

    smtp_port = int(
        os.getenv(
            "SMTP_PORT",
            "465"
        )
    )

    smtp_username = os.getenv(
        "SMTP_USERNAME",
        ""
    ).strip()

    smtp_password = os.getenv(
        "SMTP_PASSWORD",
        ""
    ).strip()

    smtp_from = os.getenv(
        "SMTP_FROM",
        smtp_username
    ).strip()

    if (
        not smtp_username
        or not smtp_password
        or not smtp_from
    ):
        raise Exception(
            "Email service is not configured. "
            "Please add SMTP settings to .env."
        )

    message = EmailMessage()

    message["Subject"] = (
        "AI Business Post Maker - Password Reset Code"
    )

    message["From"] = smtp_from
    message["To"] = receiver_email

    message.set_content(
        f"""Hello,

We received a request to reset your
AI Business Post Maker password.

Your verification code is:

{code}

This code will expire in 10 minutes.

If you did not request a password reset,
you can safely ignore this email.

AI Business Post Maker
"""
    )

    # Gmail SSL
    if smtp_port == 465:

        with smtplib.SMTP_SSL(
            smtp_host,
            smtp_port,
            timeout=20
        ) as server:

            server.login(
                smtp_username,
                smtp_password
            )

            server.send_message(
                message
            )

    # TLS / port 587
    else:

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=20
        ) as server:

            server.ehlo()

            server.starttls()

            server.ehlo()

            server.login(
                smtp_username,
                smtp_password
            )

            server.send_message(
                message
            )


# =========================================================
# FORGOT PASSWORD
# =========================================================

@app.route(
    "/api/forgot-password",
    methods=["POST"]
)
def forgot_password():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        email = (
            data.get("email") or ""
        ).strip().lower()

        if not email:

            return jsonify({
                "success": False,
                "message": "Email is required"
            }), 400

        user = User.query.filter_by(
            email=email
        ).first()

        # Security:
        # Don't reveal whether email exists.
        if not user:

            return jsonify({
                "success": True,
                "message": (
                    "If an account exists for this email, "
                    "a verification code has been sent."
                )
            }), 200

        # Invalidate previous unused codes
        PasswordResetCode.query.filter_by(
            user_id=user.id,
            used=False
        ).update(
            {
                "used": True
            },
            synchronize_session=False
        )

        # Generate 6 digit code
        code = f"{secrets.randbelow(1000000):06d}"

        # Store only hash
        code_hash = hashlib.sha256(
            code.encode("utf-8")
        ).hexdigest()

        reset_record = PasswordResetCode(
            user_id=user.id,
            code_hash=code_hash,
            expires_at=(
                datetime.utcnow()
                + timedelta(minutes=10)
            ),
            used=False
        )

        db.session.add(
            reset_record
        )

        db.session.commit()

        try:

            send_password_reset_email(
                user.email,
                code
            )

        except Exception:

            reset_record.used = True

            db.session.commit()

            raise

        return jsonify({
            "success": True,
            "message": (
                "If an account exists for this email, "
                "a verification code has been sent."
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "FORGOT PASSWORD ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to send password reset code. "
                "Please try again."
            )
        }), 500


# =========================================================
# RESET PASSWORD
# =========================================================

@app.route(
    "/api/reset-password",
    methods=["POST"]
)
def reset_password():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        email = (
            data.get("email") or ""
        ).strip().lower()

        code = (
            data.get("code") or ""
        ).strip()

        new_password = (
            data.get("new_password") or ""
        )

        if (
            not email
            or not code
            or not new_password
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Email, verification code "
                    "and new password are required"
                )
            }), 400

        if (
            not code.isdigit()
            or len(code) != 6
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Verification code must be 6 digits"
                )
            }), 400

        if len(new_password) < 8:

            return jsonify({
                "success": False,
                "message": (
                    "New password must be at least "
                    "8 characters"
                )
            }), 400

        user = User.query.filter_by(
            email=email
        ).first()

        if not user:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid or expired verification code"
                )
            }), 400

        reset_record = (
            PasswordResetCode.query
            .filter_by(
                user_id=user.id,
                used=False
            )
            .order_by(
                PasswordResetCode.id.desc()
            )
            .first()
        )

        if not reset_record:

            return jsonify({
                "success": False,
                "message": (
                    "Invalid or expired verification code"
                )
            }), 400

        # Check expiry
        if (
            reset_record.expires_at
            < datetime.utcnow()
        ):

            reset_record.used = True

            db.session.commit()

            return jsonify({
                "success": False,
                "message": (
                    "Verification code has expired. "
                    "Please request a new code."
                )
            }), 400

        submitted_hash = hashlib.sha256(
            code.encode("utf-8")
        ).hexdigest()

        if not secrets.compare_digest(
            submitted_hash,
            reset_record.code_hash
        ):

            return jsonify({
                "success": False,
                "message": (
                    "Invalid or expired verification code"
                )
            }), 400

        # Update existing user's password
        user.password_hash = (
            generate_password_hash(
                new_password
            )
        )

        # Code can never be reused
        reset_record.used = True

        db.session.commit()

        return jsonify({
            "success": True,
            "message": (
                "Password reset successfully"
            )
        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "RESET PASSWORD ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": (
                "Unable to reset password. "
                "Please try again."
            )
        }), 500
# =========================
# BUSINESS PROFILE API
# =========================

# CREATE BUSINESS PROFILE + LOGO
@app.route("/api/business-profile", methods=["POST"])
@jwt_required()
def create_business_profile():

    user_id = int(get_jwt_identity())

    try:
        # =========================
        # GET FORM DATA
        # =========================

        business_name = request.form.get("business_name")
        category = request.form.get("category")
        phone = request.form.get("phone")
        address = request.form.get("address")
        website = request.form.get("website")
        social_media_handles = request.form.get(
            "social_media_handles"
        )
        description = request.form.get("description")

        # =========================
        # VALIDATION
        # =========================

        if not business_name:
            return jsonify({
                "success": False,
                "message": "Business name is required"
            }), 400

        if not category:
            return jsonify({
                "success": False,
                "message": "Business category is required"
            }), 400

        if not phone:
            return jsonify({
                "success": False,
                "message": "Phone number is required"
            }), 400

        if not address:
            return jsonify({
                "success": False,
                "message": "Business address is required"
            }), 400

        # =========================
        # CHECK EXISTING PROFILE
        # =========================

        existing_profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if existing_profile:
            return jsonify({
                "success": False,
                "message": "Business profile already exists. Use update API."
            }), 409

        # =========================
        # LOGO UPLOAD
        # =========================

        logo_url = None

        if "logo" in request.files:

            file = request.files["logo"]

            if file.filename != "":

                result = cloudinary.uploader.upload(
                    file,
                    folder="ai_business_post_maker/business_logos"
                )

                logo_url = result.get("secure_url")

                if not logo_url:
                    return jsonify({
                        "success": False,
                        "message": "Logo upload failed"
                    }), 500

        # =========================
        # CREATE BUSINESS PROFILE
        # =========================

        profile = BusinessProfile(
            user_id=user_id,
            business_name=business_name,
            category=category,
            logo_url=logo_url,
            phone=phone,
            address=address,
            website=website,
            social_media_handles=social_media_handles,
            description=description
        )

        db.session.add(profile)
        db.session.commit()

        # =========================
        # RESPONSE
        # =========================

        return jsonify({
            "success": True,
            "message": "Business profile saved successfully",
            "business_profile": {
                "id": profile.id,
                "business_name": profile.business_name,
                "category": profile.category,
                "logo_url": profile.logo_url,
                "phone": profile.phone,
                "address": profile.address,
                "website": profile.website,
                "social_media_handles":
                    profile.social_media_handles,
                "description": profile.description
            }
        }), 201

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to save business profile"
        }), 500


# =========================
# UPDATE BUSINESS PROFILE
# =========================

@app.route("/api/business-profile", methods=["PUT"])
@jwt_required()
def update_business_profile():

    user_id = int(get_jwt_identity())

    try:

        # =========================
        # FIND USER BUSINESS PROFILE
        # =========================

        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if not profile:
            return jsonify({
                "success": False,
                "message": "Business profile not found"
            }), 404

        # =========================
        # GET FORM DATA
        # =========================

        if "business_name" in request.form:
            profile.business_name = request.form.get(
                "business_name"
            )

        if "category" in request.form:
            profile.category = request.form.get(
                "category"
            )

        if "phone" in request.form:
            profile.phone = request.form.get(
                "phone"
            )

        if "address" in request.form:
            profile.address = request.form.get(
                "address"
            )

        if "website" in request.form:
            profile.website = request.form.get(
                "website"
            )

        if "social_media_handles" in request.form:
            profile.social_media_handles = request.form.get(
                "social_media_handles"
            )

        if "description" in request.form:
            profile.description = request.form.get(
                "description"
            )

        # =========================
        # VALIDATION
        # =========================

        if not profile.business_name:
            return jsonify({
                "success": False,
                "message": "Business name is required"
            }), 400

        if not profile.category:
            return jsonify({
                "success": False,
                "message": "Business category is required"
            }), 400

        if not profile.phone:
            return jsonify({
                "success": False,
                "message": "Phone number is required"
            }), 400

        if not profile.address:
            return jsonify({
                "success": False,
                "message": "Business address is required"
            }), 400

        # =========================
        # UPDATE LOGO IF NEW LOGO
        # =========================

        if "logo" in request.files:

            file = request.files["logo"]

            if file and file.filename != "":

                result = cloudinary.uploader.upload(
                    file,
                    folder="ai_business_post_maker/business_logos"
                )

                logo_url = result.get("secure_url")

                if not logo_url:
                    return jsonify({
                        "success": False,
                        "message": "Logo upload failed"
                    }), 500

                profile.logo_url = logo_url

        # =========================
        # SAVE CHANGES
        # =========================

        db.session.commit()

        # =========================
        # RESPONSE
        # =========================

        return jsonify({

            "success": True,

            "message":
                "Business profile updated successfully",

            "business_profile": {

                "id": profile.id,

                "business_name":
                    profile.business_name,

                "category":
                    profile.category,

                "logo_url":
                    profile.logo_url,

                "phone":
                    profile.phone,

                "address":
                    profile.address,

                "website":
                    profile.website,

                "social_media_handles":
                    profile.social_media_handles,

                "description":
                    profile.description
            }

        }), 200

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": "Unable to update business profile"
        }), 500

# =========================
# GET BUSINESS PROFILE
# =========================

@app.route("/api/business-profile", methods=["GET"])
@jwt_required()
def get_business_profile():

    user_id = int(get_jwt_identity())

    try:

        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        # User ne abhi business profile create nahi ki
        if not profile:
            return jsonify({
                "success": False,
                "message": "Business profile not found"
            }), 404

        return jsonify({

            "success": True,

            "business_profile": {

                "id": profile.id,

                "business_name":
                    profile.business_name,

                "category":
                    profile.category,

                "logo_url":
                    profile.logo_url,

                "phone":
                    profile.phone,

                "address":
                    profile.address,

                "website":
                    profile.website,

                "social_media_handles":
                    profile.social_media_handles,

                "description":
                    profile.description
            }

        }), 200

    except Exception as e:

        return jsonify({
            "success": False,
            "message": "Unable to get business profile"
        }), 500


# =========================================================
# BRAND KIT
# =========================================================

@app.route("/api/brand-kit", methods=["GET"])
@jwt_required()
def get_brand_kit():

    user_id = int(get_jwt_identity())

    try:
        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if not profile:
            return jsonify({
                "success": False,
                "message": "Business profile not found"
            }), 404

        brand_kit = BrandKit.query.filter_by(
            business_profile_id=profile.id
        ).first()

        if not brand_kit:
            return jsonify({
                "success": True,
                "brand_kit": None
            }), 200

        return jsonify({
            "success": True,
            "brand_kit": {
                "id": brand_kit.id,
                "logo_url": brand_kit.logo_url,
                "brand_colors": brand_kit.brand_colors,
                "preferred_font": brand_kit.preferred_font,
                "business_name": brand_kit.business_name,
                "contact_info": brand_kit.contact_info
            }
        }), 200

    except Exception as e:
        print("Brand Kit GET Error:", str(e))

        return jsonify({
            "success": False,
            "message": "Unable to load brand kit"
        }), 500


@app.route("/api/brand-kit", methods=["POST"])
@jwt_required()
def create_brand_kit():

    user_id = int(get_jwt_identity())

    try:
        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if not profile:
            return jsonify({
                "success": False,
                "message": "Business profile not found"
            }), 404

        existing = BrandKit.query.filter_by(
            business_profile_id=profile.id
        ).first()

        if existing:
            return jsonify({
                "success": False,
                "message": "Brand kit already exists. Use PUT."
            }), 409

        data = request.get_json() or {}

        brand_colors = data.get("brand_colors")
        preferred_font = data.get("preferred_font")
        business_name = data.get(
            "business_name"
        ) or profile.business_name
        contact_info = data.get("contact_info")

        brand_kit = BrandKit(
            business_profile_id=profile.id,
            logo_url=profile.logo_url,
            brand_colors=brand_colors,
            preferred_font=preferred_font,
            business_name=business_name,
            contact_info=contact_info
        )

        db.session.add(brand_kit)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Brand kit created successfully",
            "brand_kit": {
                "id": brand_kit.id,
                "logo_url": brand_kit.logo_url,
                "brand_colors": brand_kit.brand_colors,
                "preferred_font": brand_kit.preferred_font,
                "business_name": brand_kit.business_name,
                "contact_info": brand_kit.contact_info
            }
        }), 201

    except Exception as e:

        db.session.rollback()

        print("Brand Kit POST Error:", str(e))

        return jsonify({
            "success": False,
            "message": "Unable to create brand kit"
        }), 500


@app.route("/api/brand-kit", methods=["PUT"])
@jwt_required()
def update_brand_kit():

    user_id = int(get_jwt_identity())

    try:
        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if not profile:
            return jsonify({
                "success": False,
                "message": "Business profile not found"
            }), 404

        brand_kit = BrandKit.query.filter_by(
            business_profile_id=profile.id
        ).first()

        if not brand_kit:
            return jsonify({
                "success": False,
                "message": "Brand kit not found"
            }), 404

        data = request.get_json() or {}

        if "brand_colors" in data:
            brand_kit.brand_colors = data.get(
                "brand_colors"
            )

        if "preferred_font" in data:
            brand_kit.preferred_font = data.get(
                "preferred_font"
            )

        if "business_name" in data:
            brand_kit.business_name = data.get(
                "business_name"
            )

        if "contact_info" in data:
            brand_kit.contact_info = data.get(
                "contact_info"
            )

        # Keep Brand Kit logo synchronized
        # with Business Profile logo.
        brand_kit.logo_url = profile.logo_url

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Brand kit updated successfully",
            "brand_kit": {
                "id": brand_kit.id,
                "logo_url": brand_kit.logo_url,
                "brand_colors": brand_kit.brand_colors,
                "preferred_font": brand_kit.preferred_font,
                "business_name": brand_kit.business_name,
                "contact_info": brand_kit.contact_info
            }
        }), 200

    except Exception as e:

        db.session.rollback()

        print("Brand Kit PUT Error:", str(e))

        return jsonify({
            "success": False,
            "message": "Unable to update brand kit"
        }), 500

# =========================================================
# USER CATEGORIES
# =========================================================

@app.route(
    "/api/categories",
    methods=["GET"]
)
@jwt_required()
def get_categories():
    try:
        categories = (
            Category.query
            .filter_by(is_active=True)
            .order_by(Category.name.asc())
            .all()
        )

        result = []

        for category in categories:
            result.append({
                "id": category.id,
                "name": category.name,
                "description": category.description
            })

        return jsonify({
            "success": True,
            "categories": result
        }), 200

    except Exception as e:
        print("USER CATEGORIES ERROR:", str(e))

        return jsonify({
            "success": False,
            "message": "Unable to load categories"
        }), 500

# =========================================================
# USER TEMPLATES
# =========================================================

@app.route(
    "/api/templates",
    methods=["GET"]
)
@jwt_required()
def get_templates():

    try:

        user_id = int(
            get_jwt_identity()
        )

        has_premium_access = (
            user_has_premium_templates(
                user_id
            )
        )

        templates = (
            Template.query
            .filter_by(is_active=True)
            .order_by(
                Template.id.desc()
            )
            .all()
        )

        result = []

        for template in templates:

            # Free template always available.
            # Premium template only when user
            # has premium access.

            if (
                template.is_premium
                and not has_premium_access
            ):
                continue

            result.append({
                "id": template.id,
                "category_id":
                    template.category_id,
                "name": template.name,
                "preview_url":
                    template.preview_url,
                "template_data":
                    template.template_data,
                "is_premium":
                    bool(template.is_premium)
            })

        return jsonify({
            "success": True,
            "templates": result
        }), 200

    except Exception as e:

        print(
            "USER TEMPLATES ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to load templates"
        }), 500


def download_image_from_url(url):
    if not url:
        return None
    response = requests.get(url, timeout=30)
    if response.status_code != 200:
        raise Exception("Unable to download image")
    return Image.open(BytesIO(response.content)).convert("RGBA")

def get_font(size=42, bold=False):
    possible_fonts = []
    if bold:
        possible_fonts = [
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/segoeuib.ttf",
        ]
    else:
        possible_fonts = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
        ]
    for font_path in possible_fonts:
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
    return ImageFont.load_default()

def hex_to_rgb(hex_color, default=(99, 102, 241)):
    try:
        value = hex_color.replace("#", "")
        if len(value) != 6:
            return default
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return default

def fit_image(image, width, height):
    return ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))

def add_rounded_image(base, image, box, radius=25):
    x, y, width, height = box
    image = fit_image(image, width, height)
    mask = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, width, height), radius=radius, fill=255)
    temp = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    temp.paste(image, (0, 0), mask)
    base.alpha_composite(temp, (x, y))

def draw_centered_text(image, text, y, font, fill, max_width=900):
    draw = ImageDraw.Draw(image)
    words = text.split()
    lines = []
    current = ""

    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    line_height = font.getbbox("Ag")[3] - font.getbbox("Ag")[1] + 10
    current_y = y

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        x = (image.width - width) // 2
        draw.text((x, current_y), line, font=font, fill=fill)
        current_y += line_height

    return current_y

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def hex_to_rgb(hex_str, default=(75, 60, 85)):
    """
    Convert HEX color to RGB.
    Supports:
        #FF5733
        FF5733
        #FFF
        FFF
    """

    try:
        hex_str = str(hex_str).strip().lstrip("#")

        if len(hex_str) == 3:
            hex_str = "".join(c * 2 for c in hex_str)

        if len(hex_str) != 6:
            return default

        return tuple(
            int(hex_str[i:i + 2], 16)
            for i in (0, 2, 4)
        )

    except Exception:
        return default


def download_image_from_url(url):
    """
    Download image from Cloudinary/public URL.
    Returns PIL Image or None.
    """

    if not url:
        return None

    try:
        response = requests.get(
            str(url),
            timeout=20
        )

        if response.status_code == 200:
            image = Image.open(
                BytesIO(response.content)
            )

            return image

        print(
            "Image download failed:",
            response.status_code,
            url
        )

    except Exception as e:
        print(
            "Error downloading image:",
            str(e)
        )

    return None


def get_font(size=20, bold=False):
    """
    Safely load font.
    """

    try:

        font_name = (
            "arialbd.ttf"
            if bold
            else "arial.ttf"
        )

        return ImageFont.truetype(
            font_name,
            size
        )

    except Exception:

        try:

            font_name = (
                "DejaVuSans-Bold.ttf"
                if bold
                else "DejaVuSans.ttf"
            )

            return ImageFont.truetype(
                font_name,
                size
            )

        except Exception:

            return ImageFont.load_default()


# =========================================================
# COMPLETE POST IMAGE GENERATOR
# =========================================================

def create_final_post_image(
    template_url,
    product_image_url,
    logo_url,
    business_name,
    category,
    phone,
    address,
    website,
    description,
    brand_colors,
    preferred_font,
    headline,
    cta,
    template_data
):

    # =====================================================
    # CANVAS
    # =====================================================

    CANVAS_WIDTH = 1080
    CANVAS_HEIGHT = 1080

    DESIGN_BASE_WIDTH = 1000
    DESIGN_BASE_HEIGHT = 1000

    scale_x = CANVAS_WIDTH / DESIGN_BASE_WIDTH
    scale_y = CANVAS_HEIGHT / DESIGN_BASE_HEIGHT

    # =====================================================
    # PRIMARY BRAND COLOR
    # =====================================================

    primary_color = (75, 60, 85)

    try:

        if isinstance(brand_colors, str):

            first_color = (
                brand_colors
                .split(",")[0]
                .strip()
            )

            primary_color = hex_to_rgb(
                first_color,
                default=(75, 60, 85)
            )

        elif isinstance(brand_colors, list):

            if len(brand_colors) > 0:

                primary_color = hex_to_rgb(
                    brand_colors[0],
                    default=(75, 60, 85)
                )

        elif isinstance(brand_colors, dict):

            color_value = (
                brand_colors.get("primary")
                or brand_colors.get("primary_color")
                or brand_colors.get("brand_color")
            )

            if color_value:

                primary_color = hex_to_rgb(
                    color_value,
                    default=(75, 60, 85)
                )

    except Exception as e:

        print(
            "Brand color error:",
            str(e)
        )

    # =====================================================
    # LOAD TEMPLATE
    # =====================================================

    canvas = None

    if template_url:

        try:

            canvas = download_image_from_url(
                template_url
            )

            if canvas:

                canvas = canvas.convert(
                    "RGBA"
                )

                canvas = ImageOps.fit(
                    canvas,
                    (
                        CANVAS_WIDTH,
                        CANVAS_HEIGHT
                    ),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5)
                )

        except Exception as e:

            print(
                "Template background error:",
                str(e)
            )

    # =====================================================
    # FALLBACK BACKGROUND
    # =====================================================

    if canvas is None:

        canvas = Image.new(
            "RGBA",
            (
                CANVAS_WIDTH,
                CANVAS_HEIGHT
            ),
            (248, 249, 250, 255)
        )

    draw = ImageDraw.Draw(canvas)

    # =====================================================
    # TEMPLATE DATA
    # =====================================================

    if isinstance(template_data, str):

        try:

            template_data = json.loads(
                template_data
            )

        except Exception as e:

            print(
                "Template JSON invalid:",
                str(e)
            )

            template_data = {}

    if not isinstance(
        template_data,
        dict
    ):

        template_data = {}

    # =====================================================
    # BASIC HELPERS
    # =====================================================

    def safe_int(
        value,
        default=0
    ):

        try:

            return int(
                float(value)
            )

        except Exception:

            return default

    def get_box(
        config,
        default_box
    ):

        if not isinstance(
            config,
            dict
        ):

            config = {}

        x = safe_int(
            config.get(
                "x",
                default_box[0]
            ),
            default_box[0]
        )

        y = safe_int(
            config.get(
                "y",
                default_box[1]
            ),
            default_box[1]
        )

        width = max(
            1,
            safe_int(
                config.get(
                    "width",
                    default_box[2]
                ),
                default_box[2]
            )
        )

        height = max(
            1,
            safe_int(
                config.get(
                    "height",
                    default_box[3]
                ),
                default_box[3]
            )
        )

        return (
            int(x * scale_x),
            int(y * scale_y),
            int(width * scale_x),
            int(height * scale_y)
        )

    def get_color(
        value,
        fallback
    ):

        if isinstance(
            value,
            (list, tuple)
        ):

            if len(value) >= 3:

                try:

                    return (
                        int(value[0]),
                        int(value[1]),
                        int(value[2])
                    )

                except Exception:

                    return fallback

        if isinstance(
            value,
            str
        ):

            return hex_to_rgb(
                value,
                default=fallback
            )

        return fallback

    def get_alignment(config):

        if not isinstance(
            config,
            dict
        ):

            return "left"

        alignment = str(
            config.get(
                "align",
                "left"
            )
        ).lower().strip()

        if alignment in (
            "left",
            "center",
            "right"
        ):

            return alignment

        return "left"

    def get_font_size(
        config,
        default_size
    ):

        if not isinstance(
            config,
            dict
        ):

            return max(
                8,
                int(
                    default_size *
                    scale_x
                )
            )

        base_size = safe_int(
            config.get(
                "font_size",
                default_size
            ),
            default_size
        )

        return max(
            8,
            int(
                base_size *
                scale_x
            )
        )

    def get_min_font_size(
        config,
        default_min
    ):

        if not isinstance(
            config,
            dict
        ):

            return max(
                8,
                int(
                    default_min *
                    scale_x
                )
            )

        base_min = safe_int(
            config.get(
                "min_font_size",
                default_min
            ),
            default_min
        )

        return max(
            8,
            int(
                base_min *
                scale_x
            )
        )

    # =====================================================
    # TEXT WRAPPING
    # =====================================================

    def wrap_text(
        text,
        font,
        max_width,
        max_lines=None
    ):

        text = str(
            text or ""
        ).strip()

        if not text:

            return []

        words = text.split()

        lines = []

        current_line = ""

        for word in words:

            test_line = (
                word
                if not current_line
                else current_line + " " + word
            )

            bbox = draw.textbbox(
                (0, 0),
                test_line,
                font=font
            )

            text_width = (
                bbox[2] - bbox[0]
            )

            if text_width <= max_width:

                current_line = test_line

            else:

                if current_line:

                    lines.append(
                        current_line
                    )

                current_line = word

        if current_line:

            lines.append(
                current_line
            )

        # =================================================
        # MAX LINES
        # =================================================

        if max_lines is not None:

            max_lines = max(
                1,
                safe_int(
                    max_lines,
                    1
                )
            )

            if len(lines) > max_lines:

                lines = lines[
                    :max_lines
                ]

                last_line = lines[-1]

                while last_line:

                    test = (
                        last_line.rstrip()
                        + "..."
                    )

                    bbox = draw.textbbox(
                        (0, 0),
                        test,
                        font=font
                    )

                    if (
                        bbox[2] -
                        bbox[0]
                    ) <= max_width:

                        last_line = test
                        break

                    last_line = (
                        last_line[:-1]
                        .rstrip()
                    )

                lines[-1] = last_line

        return lines

    # =====================================================
    # FIT TEXT
    # =====================================================

    def fit_text(
        text,
        box_width,
        box_height,
        config,
        default_size=40,
        bold=False
    ):

        if not text:

            return None, []

        if not isinstance(
            config,
            dict
        ):

            config = {}

        starting_size = get_font_size(
            config,
            default_size
        )

        min_size = get_min_font_size(
            config,
            max(
                10,
                default_size - 14
            )
        )

        max_lines = config.get(
            "max_lines"
        )

        if max_lines is not None:

            try:

                max_lines = int(
                    max_lines
                )

            except Exception:

                max_lines = None

        line_spacing = safe_int(
            config.get(
                "line_spacing",
                6
            ),
            6
        )

        line_spacing = int(
            line_spacing *
            scale_y
        )

        selected_font = None
        selected_lines = []

        for size in range(
            starting_size,
            min_size - 1,
            -1
        ):

            font = get_font(
                size=size,
                bold=bool(
                    config.get(
                        "bold",
                        bold
                    )
                )
            )

            lines = wrap_text(
                text,
                font,
                box_width,
                max_lines
            )

            if not lines:

                continue

            bbox = font.getbbox(
                "Ag"
            )

            line_height = (
                bbox[3] -
                bbox[1]
            ) + line_spacing

            total_height = (
                len(lines) *
                line_height
            )

            if total_height <= box_height:

                selected_font = font
                selected_lines = lines

                break

        if selected_font is None:

            selected_font = get_font(
                size=min_size,
                bold=bool(
                    config.get(
                        "bold",
                        bold
                    )
                )
            )

            selected_lines = wrap_text(
                text,
                selected_font,
                box_width,
                max_lines
            )

        return (
            selected_font,
            selected_lines
        )

    # =====================================================
    # DRAW TEXT BOX
    # =====================================================

    def draw_text_box(
        text,
        config,
        default_box,
        default_size,
        default_color,
        bold=False
    ):

        text = str(
            text or ""
        ).strip()

        if not text:

            return

        if not isinstance(
            config,
            dict
        ):

            config = {}

        x, y, width, height = get_box(
            config,
            default_box
        )

        color = get_color(
            config.get("color"),
            default_color
        )

        alignment = get_alignment(
            config
        )

        font, lines = fit_text(
            text,
            width,
            height,
            config,
            default_size,
            bold
        )

        if not font or not lines:

            return

        line_spacing = safe_int(
            config.get(
                "line_spacing",
                6
            ),
            6
        )

        line_spacing = int(
            line_spacing *
            scale_y
        )

        bbox = font.getbbox(
            "Ag"
        )

        line_height = (
            bbox[3] -
            bbox[1]
        ) + line_spacing

        current_y = y

        for line in lines:

            bbox = draw.textbbox(
                (0, 0),
                line,
                font=font
            )

            text_width = (
                bbox[2] -
                bbox[0]
            )

            if alignment == "center":

                text_x = (
                    x +
                    (width - text_width) / 2
                )

            elif alignment == "right":

                text_x = (
                    x +
                    width -
                    text_width
                )

            else:

                text_x = x

            draw.text(
                (
                    int(text_x),
                    int(current_y)
                ),
                line,
                font=font,
                fill=color
            )

            current_y += line_height

    # =====================================================
    # PLACE IMAGE
    # =====================================================

    def place_image(
        image_url,
        config,
        default_box,
        default_shape="rounded"
    ):

        if not image_url:

            return

        if not isinstance(
            config,
            dict
        ):

            config = {}

        try:

            source = download_image_from_url(
                image_url
            )

            if source is None:

                print(
                    "Could not download image:",
                    image_url
                )

                return

            source = source.convert(
                "RGBA"
            )

            x, y, width, height = get_box(
                config,
                default_box
            )

            fit_mode = str(
                config.get(
                    "fit",
                    "cover"
                )
            ).lower()

            shape = str(
                config.get(
                    "shape",
                    default_shape
                )
            ).lower()

            radius = safe_int(
                config.get(
                    "radius",
                    28
                ),
                28
            )

            radius = int(
                radius *
                scale_x
            )

            # =============================================
            # CONTAIN
            # =============================================

            if fit_mode == "contain":

                contained = ImageOps.contain(
                    source,
                    (
                        width,
                        height
                    ),
                    method=Image.Resampling.LANCZOS
                )

                image_layer = Image.new(
                    "RGBA",
                    (
                        width,
                        height
                    ),
                    (
                        255,
                        255,
                        255,
                        0
                    )
                )

                offset_x = (
                    width -
                    contained.width
                ) // 2

                offset_y = (
                    height -
                    contained.height
                ) // 2

                image_layer.alpha_composite(
                    contained,
                    (
                        offset_x,
                        offset_y
                    )
                )

            # =============================================
            # COVER
            # =============================================

            else:

                image_layer = ImageOps.fit(
                    source,
                    (
                        width,
                        height
                    ),
                    method=Image.Resampling.LANCZOS,
                    centering=(0.5, 0.5)
                )

            # =============================================
            # MASK
            # =============================================

            mask = Image.new(
                "L",
                (
                    width,
                    height
                ),
                0
            )

            mask_draw = ImageDraw.Draw(
                mask
            )

            if shape == "circle":

                diameter = min(
                    width,
                    height
                )

                circle_x = (
                    width -
                    diameter
                ) // 2

                circle_y = (
                    height -
                    diameter
                ) // 2

                mask_draw.ellipse(
                    (
                        circle_x,
                        circle_y,
                        circle_x + diameter,
                        circle_y + diameter
                    ),
                    fill=255
                )

            elif shape == "rounded":

                radius = max(
                    0,
                    min(
                        radius,
                        min(
                            width,
                            height
                        ) // 2
                    )
                )

                mask_draw.rounded_rectangle(
                    (
                        0,
                        0,
                        width,
                        height
                    ),
                    radius=radius,
                    fill=255
                )

            else:

                mask_draw.rectangle(
                    (
                        0,
                        0,
                        width,
                        height
                    ),
                    fill=255
                )

            temp = Image.new(
                "RGBA",
                (
                    width,
                    height
                ),
                (
                    255,
                    255,
                    255,
                    0
                )
            )

            temp.paste(
                image_layer,
                (0, 0),
                mask
            )

            canvas.alpha_composite(
                temp,
                (
                    x,
                    y
                )
            )

        except Exception as e:

            print(
                "Image placement error:",
                str(e)
            )

    # =====================================================
    # TEMPLATE CONFIGURATION
    # =====================================================

    product_config = (
        template_data.get(
            "product_image"
        )
        or template_data.get(
            "image_box"
        )
        or {}
    )

    logo_config = (
        template_data.get(
            "logo"
        )
        or {}
    )

    business_config = (
        template_data.get(
            "business_name"
        )
        or {}
    )

    headline_config = (
        template_data.get(
            "headline"
        )
        or {}
    )

    body_config = (
        template_data.get(
            "body"
        )
        or template_data.get(
            "description"
        )
        or {}
    )

    cta_config = (
        template_data.get(
            "cta"
        )
        or {}
    )

    contact_config = (
        template_data.get(
            "contact"
        )
        or {}
    )

    # =====================================================
    # 1. PRODUCT IMAGE
    # =====================================================

    place_image(
        product_image_url,
        product_config,
        default_box=(
            555,
            275,
            375,
            470
        ),
        default_shape="rounded"
    )

    # =====================================================
    # 2. LOGO
    # =====================================================

    place_image(
        logo_url,
        logo_config,
        default_box=(
            405,
            62,
            70,
            70
        ),
        default_shape="circle"
    )

    # =====================================================
    # 3. BUSINESS NAME
    # =====================================================

    draw_text_box(
        business_name,
        business_config,
        default_box=(
            485,
            67,
            330,
            60
        ),
        default_size=28,
        default_color=primary_color,
        bold=True
    )

    # =====================================================
    # 4. HEADLINE
    # =====================================================

    draw_text_box(
        headline,
        headline_config,
        default_box=(
            70,
            265,
            445,
            145
        ),
        default_size=43,
        default_color=primary_color,
        bold=True
    )

    # =====================================================
    # 5. DESCRIPTION
    # =====================================================

    clean_description = str(
        description or ""
    ).strip()

    # Remove accidental AI conversation text
    clean_description = (
        clean_description
        .replace(
            "AI Mode conversation:",
            ""
        )
        .strip()
    )

    draw_text_box(
        clean_description,
        body_config,
        default_box=(
            70,
            425,
            445,
            175
        ),
        default_size=19,
        default_color=(
            68,
            51,
            72
        ),
        bold=False
    )

    # =====================================================
    # 6. CTA
    # =====================================================

    if cta:

        cta_str = str(
            cta
        ).strip()

        # Keep CTA short.
        if (
            "@" in cta_str
            or (
                any(
                    char.isdigit()
                    for char in cta_str
                )
                and len(cta_str) > 10
            )
            or len(cta_str) > 25
        ):

            cta_str = "Shop Now"

        cta_x, cta_y, cta_w, cta_h = get_box(
            cta_config,
            (
                70,
                560,
                200,
                44
            )
        )

        cta_background = get_color(
            cta_config.get(
                "background"
            ),
            (
                59,
                20,
                67
            )
        )

        radius = int(
            8 * scale_x
        )

        draw.rounded_rectangle(
            (
                cta_x,
                cta_y,
                cta_x + cta_w,
                cta_y + cta_h
            ),
            radius=radius,
            fill=cta_background,
            outline=cta_background
        )

        cta_color = get_color(
            cta_config.get(
                "color"
            ),
            (
                255,
                255,
                255
            )
        )

        cta_font_size = get_font_size(
            cta_config,
            15
        )

        cta_font = get_font(
            size=cta_font_size,
            bold=True
        )

        bbox = draw.textbbox(
            (0, 0),
            cta_str,
            font=cta_font
        )

        text_width = (
            bbox[2] -
            bbox[0]
        )

        text_height = (
            bbox[3] -
            bbox[1]
        )

        text_x = (
            cta_x +
            (cta_w - text_width) / 2
        )

        text_y = (
            cta_y +
            (cta_h - text_height) / 2
            - 2
        )

        draw.text(
            (
                int(text_x),
                int(text_y)
            ),
            cta_str,
            font=cta_font,
            fill=cta_color
        )

    # =====================================================
    # 7. CONTACT INFORMATION
    # =====================================================

    contact_x, contact_y, contact_width, contact_height = get_box(
        contact_config,
        (
            70,
            615,
            445,
            100
        )
    )

    contact_color = get_color(
        contact_config.get(
            "color"
        ),
        (
            59,
            20,
            67
        )
    )

    contact_font_size = get_font_size(
        contact_config,
        14
    )

    contact_font = get_font(
        size=contact_font_size,
        bold=True
    )

    current_contact_y = contact_y

    line_height = (
        contact_font_size
        + int(4 * scale_y)
    )

    # =====================================================
    # PHONE
    # =====================================================

    if phone:

        phone_text = (
            f"Phone: {str(phone).strip()}"
        )

        contact_lines = wrap_text(
            phone_text,
            contact_font,
            contact_width
        )

        for line in contact_lines:

            draw.text(
                (
                    contact_x,
                    current_contact_y
                ),
                line,
                font=contact_font,
                fill=contact_color
            )

            current_contact_y += (
                line_height
            )

    # =====================================================
    # WEBSITE
    # =====================================================

    if website:

        website_text = (
            f"Web: {str(website).strip()}"
        )

        contact_lines = wrap_text(
            website_text,
            contact_font,
            contact_width
        )

        for line in contact_lines:

            draw.text(
                (
                    contact_x,
                    current_contact_y
                ),
                line,
                font=contact_font,
                fill=contact_color
            )

            current_contact_y += (
                line_height
            )

    # =====================================================
    # ADDRESS
    # =====================================================

    if address:

        address_text = (
            f"Address: {str(address).strip()}"
        )

        contact_lines = wrap_text(
            address_text,
            contact_font,
            contact_width
        )

        for line in contact_lines:

            draw.text(
                (
                    contact_x,
                    current_contact_y
                ),
                line,
                font=contact_font,
                fill=contact_color
            )

            current_contact_y += (
                line_height
            )

    # =====================================================
    # SAVE IMAGE TO MEMORY
    # =====================================================

    output = BytesIO()

    canvas.convert(
        "RGB"
    ).save(
        output,
        format="PNG",
        optimize=True
    )

    output.seek(0)

    return output

# =========================================================
# EDIT / REGENERATE EXISTING POST
# =========================================================

@app.route("/regenerate-post", methods=["POST"])
@jwt_required()
def regenerate_post():

    try:

        user_id = int(get_jwt_identity())

        print("")
        print("========================================")
        print("REGENERATE EXISTING POST REQUEST")
        print("========================================")

        # =====================================================
        # 1. READ MULTIPART FORM DATA
        # =====================================================

        project_id = request.form.get("project_id")
        post_id = request.form.get("post_id")

        print("PROJECT ID:", project_id)
        print("POST ID:", post_id)

        if not project_id and not post_id:
            return jsonify({
                "success": False,
                "message": (
                    "Project ID or Post ID is required. "
                    "Please generate the post again from Create Post."
                )
            }), 400

        # =====================================================
        # 2. CONVERT IDS
        # =====================================================

        if project_id:
            try:
                project_id = int(project_id)
            except Exception:
                project_id = None

        if post_id:
            try:
                post_id = int(post_id)
            except Exception:
                post_id = None

        # =====================================================
        # 3. FIND ORIGINAL PROJECT
        # =====================================================

        project = None
        post = None

        if project_id:

            project = Project.query.filter_by(
                id=project_id,
                user_id=user_id
            ).first()

        # =====================================================
        # 4. IF PROJECT NOT FOUND, FIND THROUGH POST
        # =====================================================

        if not project and post_id:

            post = Post.query.filter_by(
                id=post_id,
                user_id=user_id
            ).first()

            if post and post.project_id:

                project = Project.query.filter_by(
                    id=post.project_id,
                    user_id=user_id
                ).first()

        if not project:

            return jsonify({
                "success": False,
                "message": (
                    "Original project not found. "
                    "Please generate the post again from Create Post."
                )
            }), 404

        # =====================================================
        # 5. FIND EXACT ORIGINAL POST
        # =====================================================

        if post_id:

            post = Post.query.filter_by(
                id=post_id,
                project_id=project.id,
                user_id=user_id
            ).first()

        # If post_id was not available, get the post
        # belonging to this project.
        if not post:

            post = Post.query.filter_by(
                project_id=project.id,
                user_id=user_id
            ).order_by(
                Post.id.desc()
            ).first()

        if not post:

            return jsonify({
                "success": False,
                "message": (
                    "Original post not found. "
                    "Please generate the post again from Create Post."
                )
            }), 404

        # =====================================================
        # 6. GET CURRENT BUSINESS PROFILE
        # =====================================================

        profile = BusinessProfile.query.filter_by(
            user_id=user_id
        ).first()

        if not profile:

            return jsonify({
                "success": False,
                "message": "Business profile not found."
            }), 404

        # =====================================================
        # 7. GET BRAND KIT
        # =====================================================

        brand_kit = BrandKit.query.filter_by(
            business_profile_id=profile.id
        ).first()

        # =====================================================
        # 8. LOAD ORIGINAL SAVED DESIGN SNAPSHOT
        #
        # This is important.
        #
        # We first use the data saved with the original project.
        # Therefore editing does NOT accidentally use a newer
        # business profile/template/brand setting.
        # =====================================================

        original_design = {}

        if project.design_data:

            try:

                original_design = json.loads(
                    project.design_data
                )

                if not isinstance(
                    original_design,
                    dict
                ):
                    original_design = {}

            except Exception:

                original_design = {}

        # =====================================================
        # 9. GET ORIGINAL TEMPLATE
        # =====================================================

        template = None

        if project.template_id:

            template = Template.query.filter_by(
                id=project.template_id
            ).first()

        if not template:

            return jsonify({
                "success": False,
                "message": (
                    "Original template data is missing. "
                    "Please generate the post again from Create Post."
                )
            }), 400

        # =====================================================
        # 10. ORIGINAL TEMPLATE DATA
        #
        # Prefer saved original template_data.
        # Fallback to DB template if old project does not
        # contain snapshot data.
        # =====================================================

        template_data = (
            original_design.get("template_data")
            if original_design.get("template_data")
            else template.template_data
        )

        if not template_data:

            return jsonify({
                "success": False,
                "message": (
                    "Original template layout data is missing. "
                    "Please generate the post again from Create Post."
                )
            }), 400

        # =====================================================
        # 11. ORIGINAL TEMPLATE URL
        # =====================================================

        template_url = (
            original_design.get("template_url")
            or template.preview_url
            or ""
        )

        # =====================================================
        # 12. ORIGINAL PRODUCT IMAGE
        #
        # post.product_image_url is the REAL product image.
        # image_url is the FINAL GENERATED POST IMAGE.
        # =====================================================

        product_image_url = (
            post.product_image_url
            or original_design.get(
                "product_image_url"
            )
            or ""
        )

        # =====================================================
        # 13. NEW PRODUCT IMAGE - OPTIONAL
        #
        # If user selected a new image:
        #     upload new image
        #     replace product_image_url
        #
        # If user did NOT select one:
        #     keep original product image.
        # =====================================================

        new_product_file = request.files.get(
            "product_image"
        )

        if (
            new_product_file
            and new_product_file.filename
            and new_product_file.filename.strip()
        ):

            print(
                "NEW PRODUCT IMAGE RECEIVED:",
                new_product_file.filename
            )

            product_upload = (
                cloudinary.uploader.upload(
                    new_product_file,
                    folder=(
                        "ai_business_post_maker/"
                        "product_images"
                    ),
                    resource_type="image"
                )
            )

            uploaded_product_url = (
                product_upload.get(
                    "secure_url"
                )
            )

            if not uploaded_product_url:

                return jsonify({
                    "success": False,
                    "message": (
                        "New product image upload failed."
                    )
                }), 500

            product_image_url = (
                uploaded_product_url
            )

        if not product_image_url:

            return jsonify({
                "success": False,
                "message": (
                    "Original product image is missing. "
                    "Please select a product image."
                )
            }), 400

        # =====================================================
        # 14. ORIGINAL BUSINESS / BRAND DATA
        #
        # Use saved original snapshot first.
        # This keeps the original post design unchanged.
        # =====================================================

        logo_url = (
            original_design.get(
                "logo_url"
            )
            or profile.logo_url
            or ""
        )

        business_name = (
            original_design.get(
                "business_name"
            )
            or (
                brand_kit.business_name
                if brand_kit
                and brand_kit.business_name
                else profile.business_name
            )
            or ""
        )

        category = (
            original_design.get(
                "category"
            )
            or profile.category
            or ""
        )

        original_phone = (
            original_design.get(
                "phone"
            )
            or profile.phone
            or ""
        )

        address = (
            original_design.get(
                "address"
            )
            or profile.address
            or ""
        )

        website = (
            original_design.get(
                "website"
            )
            or profile.website
            or ""
        )

        brand_colors = (
            original_design.get(
                "brand_colors"
            )
            if original_design.get(
                "brand_colors"
            ) is not None
            else (
                brand_kit.brand_colors
                if brand_kit
                else ""
            )
        )

        preferred_font = (
            original_design.get(
                "preferred_font"
            )
            if original_design.get(
                "preferred_font"
            ) is not None
            else (
                brand_kit.preferred_font
                if brand_kit
                else ""
            )
        )

        original_contact = (
            original_design.get(
                "contact"
            )
            or (
                brand_kit.contact_info
                if brand_kit
                else original_phone
            )
            or ""
        )

        # =====================================================
        # 15. EDITABLE PHONE / CONTACT
        #
        # User can change the number on Edit screen.
        # This DOES NOT change BusinessProfile globally.
        # It only changes this generated post.
        # =====================================================

        if "contact" in request.form:

            phone = (
                request.form.get(
                    "contact"
                ) or ""
            ).strip()

        else:

            phone = original_phone

        contact_info = phone or original_contact

        # =====================================================
        # 16. EDITED TEXT
        #
        # If field exists -> use edited value.
        # Otherwise -> use original saved value.
        # =====================================================

        if "headline" in request.form:

            headline = (
                request.form.get(
                    "headline"
                ) or ""
            ).strip()

        else:

            headline = (
                original_design.get(
                    "headline"
                )
                or post.headline
                or ""
            )

        if "caption" in request.form:

            caption = (
                request.form.get(
                    "caption"
                ) or ""
            ).strip()

        else:

            caption = (
                original_design.get(
                    "caption"
                )
                or post.caption
                or ""
            )

        if "description" in request.form:

            description = (
                request.form.get(
                    "description"
                ) or ""
            ).strip()

        else:

            description = (
                original_design.get(
                    "description"
                )
                or caption
                or ""
            )

        if "hashtags" in request.form:

            hashtags = (
                request.form.get(
                    "hashtags"
                ) or ""
            ).strip()

        else:

            hashtags = (
                original_design.get(
                    "hashtags"
                )
                or post.hashtags
                or ""
            )

        if "cta" in request.form:

            cta = (
                request.form.get(
                    "cta"
                ) or ""
            ).strip()

        else:

            cta = (
                original_design.get(
                    "cta"
                )
                or post.call_to_action
                or ""
            )

        # =====================================================
        # 17. GENERATE SAME TEMPLATE AGAIN
        #
        # IMPORTANT:
        # No new template is selected.
        # No new project is created.
        # No new post is created.
        # =====================================================

        final_image = create_final_post_image(

            template_url=template_url,

            product_image_url=product_image_url,

            logo_url=logo_url,

            business_name=business_name,

            category=category,

            phone=phone,

            address=address,

            website=website,

            description=description,

            brand_colors=brand_colors,

            preferred_font=preferred_font,

            headline=headline,

            cta=cta,

            template_data=template_data
        )

        if final_image is None:

            raise Exception(
                "Unable to create final post image."
            )

        # =====================================================
        # 18. UPLOAD NEW FINAL POST IMAGE
        # =====================================================

        final_image.seek(0)

        upload_resp = (
            cloudinary.uploader.upload(
                final_image,
                folder=(
                    "ai_business_post_maker/"
                    "generated_posts"
                ),
                resource_type="image"
            )
        )

        new_image_url = (
            upload_resp.get(
                "secure_url"
            )
        )

        if not new_image_url:

            raise Exception(
                "Regenerated image upload failed."
            )

        # =====================================================
        # 19. UPDATE SAME POST
        #
        # DO NOT CREATE NEW POST.
        # =====================================================

        post.headline = headline

        post.caption = caption

        post.promotional_text = caption

        post.hashtags = hashtags

        post.call_to_action = cta

        post.product_image_url = (
            product_image_url
        )

        post.image_url = new_image_url

        post.download_url = new_image_url

        # Keep original project settings.
        if project.language:

            post.language = (
                project.language
            )

        if project.content_type:

            post.content_type = (
                project.content_type
            )

        if project.platform:

            post.platform = (
                project.platform
            )

        post.updated_at = datetime.utcnow()

        # =====================================================
        # 20. UPDATE SAME PROJECT
        # =====================================================

        if headline:

            project.title = headline

        # =====================================================
        # 21. PRESERVE ORIGINAL DESIGN DATA
        #
        # Start from old snapshot so unrelated information
        # does not disappear.
        # =====================================================

        updated_design = dict(
            original_design
        )

        updated_design.update({

            "template_id":
                template.id,

            "template_name":
                template.name,

            "template_url":
                template_url,

            "template_data":
                template_data,

            "product_image_url":
                product_image_url,

            "logo_url":
                logo_url,

            "business_name":
                business_name,

            "category":
                category,

            "phone":
                phone,

            "address":
                address,

            "website":
                website,

            "brand_colors":
                brand_colors,

            "preferred_font":
                preferred_font,

            "contact":
                contact_info,

            "headline":
                headline,

            "caption":
                caption,

            "description":
                description,

            "hashtags":
                hashtags,

            "cta":
                cta,

            "image_url":
                new_image_url,

            "download_url":
                new_image_url
        })

        project.design_data = json.dumps(
            updated_design
        )

        # =====================================================
        # 22. SAVE
        # =====================================================

        db.session.commit()

        # =====================================================
        # 23. RETURN COMPLETE UPDATED RESULT
        # =====================================================

        return jsonify({

            "success":
                True,

            "status":
                "success",

            "message":
                "Post successfully regenerated.",

            "project_id":
                project.id,

            "post_id":
                post.id,

            "result": {

                "project_id":
                    project.id,

                "post_id":
                    post.id,

                "headline":
                    headline,

                "caption":
                    caption,

                "description":
                    description,

                "hashtags":
                    hashtags,

                "cta":
                    cta,

                "image_url":
                    new_image_url,

                "download_url":
                    new_image_url,

                "template_id":
                    template.id,

                "template_name":
                    template.name,

                "template_url":
                    template_url,

                "template_data":
                    template_data,

                "product_image_url":
                    product_image_url,

                "logo_url":
                    logo_url,

                "business_name":
                    business_name,

                "category":
                    category,

                "phone":
                    phone,

                "address":
                    address,

                "website":
                    website,

                "brand_colors":
                    brand_colors,

                "preferred_font":
                    preferred_font,

                "contact":
                    contact_info
            }

        }), 200

    except Exception as e:

        db.session.rollback()

        import traceback

        traceback.print_exc()

        return jsonify({

            "success":
                False,

            "status":
                "error",

            "message":
                "Post regeneration failed.",

            "error":
                str(e)

        }), 500
# =========================================================
# AI GENERATION LIMIT CHECK
# =========================================================
#
# Is helper ko generate_complete_post()
# ke start mein call karna hai.
# =========================================================

def check_ai_generation_limit(user_id):

    today = datetime.utcnow().date()

    first_day = today.replace(
        day=1
    )

    subscription = (
        Subscription.query
        .filter_by(user_id=user_id)
        .order_by(
            Subscription.id.desc()
        )
        .first()
    )

    free_plan = SubscriptionPlan.query.filter_by(
        name="Free"
    ).first()

    plan = free_plan

    if subscription:

        active = (
            subscription.status == "active"
            and (
                subscription.end_date is None
                or subscription.end_date >= datetime.utcnow()
            )
        )

        if active:

            subscription_plan = (
                SubscriptionPlan.query.filter_by(
                    id=subscription.plan_id
                ).first()
            )

            if subscription_plan:

                plan = subscription_plan

    if not plan:

        raise Exception(
            "Subscription plan not configured"
        )

    usage_records = (
        AIUsage.query
        .filter(
            AIUsage.user_id == user_id,
            AIUsage.usage_date >= first_day,
            AIUsage.usage_date <= today,
        )
        .all()
    )

    used = sum(
        record.generation_count or 0
        for record in usage_records
    )

    limit = (
        plan.ai_generation_limit
        if plan.ai_generation_limit is not None
        else 10
    )

    if used >= limit:

        return {
            "allowed": False,
            "used": used,
            "limit": limit,
            "remaining": 0,
            "plan": plan.name,
        }

    return {
        "allowed": True,
        "used": used,
        "limit": limit,
        "remaining": limit - used,
        "plan": plan.name,
    }
# =========================================================
# FINAL AI POST GENERATION ROUTE
# =========================================================


@app.route(
    "/api/ai/generate-complete-post",
    methods=["POST"]
)
@jwt_required()
def generate_complete_post():

    try:

        user_id = int(
            get_jwt_identity()
        )

        # =================================================
        # AI USAGE / SUBSCRIPTION CHECK
        # =================================================

        usage_status = check_ai_generation_limit(
            user_id
        )

        if not usage_status["allowed"]:

            return jsonify({

                "success": False,

                "message":
                    "You have reached your monthly AI generation limit.",

                "usage":
                    usage_status,

                "upgrade_required":
                    usage_status["plan"] == "Free",

            }), 403

        user_id = int(get_jwt_identity())
        prompt = (request.form.get("prompt") or "").strip()
        content_type = request.form.get("content_type") or "Promotional"
        format_type = request.form.get("format") or "Instagram Post"
        language = request.form.get("language") or "English"
        tone = request.form.get("tone") or "Professional"
        template_id = request.form.get("template_id")

        if not prompt:
            return jsonify({"success": False, "message": "Product description is required"}), 400

        profile = BusinessProfile.query.filter_by(user_id=user_id).first()
        if not profile:
            return jsonify({"success": False, "message": "Please create business profile first"}), 400

        brand_kit = BrandKit.query.filter_by(business_profile_id=profile.id).first()

        try:
            template = Template.query.filter_by(id=int(template_id), is_active=True).first() if template_id else None
        except:
            template = None

        if "product_image" not in request.files:
            return jsonify({"success": False, "message": "Product image is required"}), 400

        product_file = request.files["product_image"]
        if not product_file or product_file.filename == "":
            return jsonify({"success": False, "message": "Please select product image"}), 400

        product_result = cloudinary.uploader.upload(product_file, folder="ai_business_post_maker/product_images")
        product_image_url = product_result.get("secure_url")

        if not product_image_url:
            return jsonify({"success": False, "message": "Product image upload failed"}), 500

        brand_colors = brand_kit.brand_colors if brand_kit else ""
        preferred_font = brand_kit.preferred_font if brand_kit else ""
        contact_info = brand_kit.contact_info if brand_kit else profile.phone
        brand_name = brand_kit.business_name if brand_kit and brand_kit.business_name else profile.business_name

        ai_prompt = f"""
You are an expert social media marketing copywriter.
Create engaging, professional marketing copy for a real business social media post based on the user's input. Do NOT repeat or include user chatting instructions or raw prompts in the output description.

BUSINESS:
Name: {brand_name}
Category: {profile.category}
Phone: {profile.phone}
Address: {profile.address}
Website: {profile.website}
Description: {profile.description}

BRAND KIT:
Colors: {brand_colors}
Font: {preferred_font}
Contact: {contact_info}

USER PRODUCT/POST REQUEST:
{prompt}

SETTINGS:
Content Type: {content_type}
Platform: {format_type}
Language: {language}
Tone: {tone}

RULES:
- Write in {language}.
- Create short, punchy marketing copy. Do not copy user chat instructions into the description.
- Create catchy headline.
- Create useful marketing description/caption.
- Give relevant hashtags.
- Create a clear, actionable CTA.
- Return ONLY valid JSON format.

Return:
{{
    "headline": "...",
    "caption": "...",
    "hashtags": "#tag1 #tag2 #tag3",
    "cta": "..."
}}
"""

        response = ai_client.models.generate_content(
            model="gemini-3.6-flash",
            contents=ai_prompt
        )

        raw_text = (response.text or "").strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json", 1)[1].split("```", 1)[0].strip()
        elif "```" in raw_text:
            raw_text = raw_text.split("```", 1)[1].split("```", 1)[0].strip()

        try:
            generated_result = json.loads(raw_text)
        except:
            generated_result = {
                "headline": "Exclusive Collection",
                "caption": raw_text,
                "hashtags": "#Business #Offer",
                "cta": "Shop Now"
            }

        final_image = create_final_post_image(
            template_url=template.preview_url if template else "",
            product_image_url=product_image_url,
            logo_url=profile.logo_url,
            business_name=brand_name,
            category=profile.category,
            phone=profile.phone,
            address=profile.address,
            website=profile.website,
            description=generated_result.get("caption", profile.description),
            brand_colors=brand_colors,
            preferred_font=preferred_font,
            headline=generated_result.get("headline", ""),
            cta=generated_result.get("cta", ""),
            template_data=template.template_data if template else {}
        )

        final_result = cloudinary.uploader.upload(
            final_image,
            folder="ai_business_post_maker/generated_posts",
            resource_type="image"
        )
        final_image_url = final_result.get("secure_url")

        if not final_image_url:
            raise Exception("Final image upload failed")

        project = Project(
            user_id=user_id,
            business_profile_id=profile.id,
            template_id=template.id if template else None,
            title=generated_result.get("headline", "AI Generated Post"),
            content_type=content_type,
            platform=format_type,
            language=language,
            tone=tone,
            design_data=json.dumps({
    "template_id":
        template.id if template else None,

    "template_name":
        template.name
        if template
        else "Designer Brand Post",

    "template_url":
        template.preview_url
        if template
        else "",

    "template_data":
        template.template_data
        if template
        else {},

    "product_image_url":
        product_image_url,

    "final_image_url":
        final_image_url,

    "image_url":
        final_image_url,

    "download_url":
        final_image_url,

    "logo_url":
        profile.logo_url or "",

    "business_name":
        brand_name or "",

    "category":
        profile.category or "",

    "phone":
        profile.phone or "",

    "address":
        profile.address or "",

    "website":
        profile.website or "",

    "brand_colors":
        brand_colors or "",

    "preferred_font":
        preferred_font or "",

    "contact":
        contact_info or "",

    "headline":
        generated_result.get(
            "headline",
            ""
        ),

    "caption":
        generated_result.get(
            "caption",
            ""
        ),

    "description":
        generated_result.get(
            "caption",
            profile.description or ""
        ),

    "hashtags":
        generated_result.get(
            "hashtags",
            ""
        ),

    "cta":
        generated_result.get(
            "cta",
            ""
        )
}),
            status="saved"
        )

        db.session.add(project)
        db.session.flush()

        new_post = Post(
            user_id=user_id,
            project_id=project.id,
            headline=generated_result.get("headline"),
            caption=generated_result.get("caption"),
            promotional_text=generated_result.get("caption"),
            hashtags=generated_result.get("hashtags"),
            call_to_action=generated_result.get("cta"),
            language=language,
            content_type=content_type,
            platform=format_type,
            product_image_url=product_image_url,
            image_url=final_image_url,
            download_url=final_image_url
        )

        db.session.add(new_post)
        db.session.add(AIUsage(
            user_id=user_id,
            generation_type="social_post",
            generation_count=1,
            usage_date=datetime.utcnow().date()
        ))
        db.session.commit()

        return jsonify({
    "success": True,
    "message": "Final post generated successfully",

    # IDs are VERY IMPORTANT for Edit/Regenerate
    "project_id": project.id,
    "post_id": new_post.id,

    "result": {
        # AI text
        "headline": generated_result.get("headline", ""),
        "caption": generated_result.get("caption", ""),
        "description": generated_result.get(
            "caption",
            profile.description or ""
        ),
        "hashtags": generated_result.get("hashtags", ""),
        "cta": generated_result.get("cta", ""),

        # Final generated image
        "image_url": final_image_url,
        "download_url": final_image_url,

        # ORIGINAL TEMPLATE INFORMATION
        "template_id": template.id if template else None,
        "template_name": (
            template.name
            if template
            else "Designer Brand Post"
        ),
        "template_url": (
            template.preview_url
            if template
            else ""
        ),
        "template_data": (
            template.template_data
            if template
            else {}
        ),

        # ORIGINAL PRODUCT IMAGE
        "product_image_url": product_image_url,

        # BUSINESS PROFILE
        "logo_url": profile.logo_url or "",
        "business_name": brand_name or "",
        "category": profile.category or "",
        "phone": profile.phone or "",
        "address": profile.address or "",
        "website": profile.website or "",

        # BRAND KIT
        "brand_colors": brand_colors or "",
        "preferred_font": preferred_font or "",
        "contact": contact_info or ""
    }
}), 200
    except Exception as e:
        db.session.rollback()
        print("ERROR:", str(e))
        return jsonify({"success": False, "message": "AI post generation failed", "error": str(e)}), 500


# # =========================================================
# PROJECT HISTORY
# =========================================================

@app.route("/api/projects", methods=["GET"])
@jwt_required()
def get_projects():

    try:

        user_id = int(get_jwt_identity())

        projects = (
            Project.query
            .filter_by(user_id=user_id)
            .order_by(Project.id.desc())
            .all()
        )

        result = []

        for project in projects:

            post = Post.query.filter_by(
                project_id=project.id
            ).first()

            template = None

            if project.template_id:
                template = Template.query.filter_by(
                    id=project.template_id
                ).first()

            result.append({

                "project_id": project.id,

                "title":
                    project.title or "Untitled Project",

                "content_type":
                    project.content_type or "",

                "platform":
                    project.platform or "",

                "language":
                    project.language or "",

                "tone":
                    project.tone or "",

                "status":
                    project.status or "saved",

                "template_name":
                    template.name
                    if template
                    else "Custom Brand Post",

                "image_url":
                    post.image_url
                    if post
                    else "",

                "download_url":
                    post.download_url
                    if post
                    else "",

                "product_image_url":
                    post.product_image_url
                    if post
                    else "",

                "headline":
                    post.headline
                    if post
                    else "",

                "caption":
                    post.caption
                    if post
                    else "",

                "hashtags":
                    post.hashtags
                    if post
                    else "",

                "cta":
                    post.call_to_action
                    if post
                    else "",

                "created_at":
                    post.created_at.isoformat()
                    if post and post.created_at
                    else ""
            })

        return jsonify({

            "success": True,

            "projects": result

        }), 200

    except Exception as e:

        print(
            "PROJECT HISTORY ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load projects"

        }), 500


# =========================================================
# SINGLE PROJECT
# =========================================================

@app.route(
    "/api/projects/<int:project_id>",
    methods=["GET"]
)
@jwt_required()
def get_single_project(project_id):

    try:

        user_id = int(
            get_jwt_identity()
        )

        project = Project.query.filter_by(
            id=project_id,
            user_id=user_id
        ).first()

        if not project:

            return jsonify({

                "success": False,

                "message":
                    "Project not found"

            }), 404

        post = Post.query.filter_by(
            project_id=project.id
        ).first()

        template = None

        if project.template_id:

            template = Template.query.filter_by(
                id=project.template_id
            ).first()

        return jsonify({

            "success": True,

            "project": {

                "project_id":
                    project.id,

                "title":
                    project.title or "",

                "content_type":
                    project.content_type or "",

                "platform":
                    project.platform or "",

                "language":
                    project.language or "",

                "tone":
                    project.tone or "",

                "status":
                    project.status or "saved",

                "template_id":
                    project.template_id,

                "template_name":
                    template.name
                    if template
                    else "Custom Brand Post",

                "template_preview_url":
                    template.preview_url
                    if template
                    else "",

                "image_url":
                    post.image_url
                    if post
                    else "",

                "download_url":
                    post.download_url
                    if post
                    else "",

                "product_image_url":
                    post.product_image_url
                    if post
                    else "",

                "headline":
                    post.headline
                    if post
                    else "",

                "caption":
                    post.caption
                    if post
                    else "",

                "hashtags":
                    post.hashtags
                    if post
                    else "",

                "cta":
                    post.call_to_action
                    if post
                    else "",

                "created_at":
                    post.created_at.isoformat()
                    if post and post.created_at
                    else "",

                "updated_at":
                    post.updated_at.isoformat()
                    if post and post.updated_at
                    else ""
            }

        }), 200

    except Exception as e:

        print(
            "SINGLE PROJECT ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load project"

        }), 500


# =========================================================
# DELETE PROJECT
# =========================================================

@app.route(
    "/api/projects/<int:project_id>",
    methods=["DELETE"]
)
@jwt_required()
def delete_project(project_id):

    try:

        user_id = int(
            get_jwt_identity()
        )

        project = Project.query.filter_by(
            id=project_id,
            user_id=user_id
        ).first()

        if not project:

            return jsonify({

                "success": False,

                "message":
                    "Project not found"

            }), 404

        # Delete post first because
        # post contains project_id
        Post.query.filter_by(
            project_id=project.id
        ).delete(
            synchronize_session=False
        )

        # Delete project
        db.session.delete(project)

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Project deleted successfully"

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "DELETE PROJECT ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to delete project"

        }), 500


# =========================================================
# COPY / DUPLICATE PROJECT
# =========================================================

@app.route(
    "/api/projects/<int:project_id>/copy",
    methods=["POST"]
)
@jwt_required()
def copy_project(project_id):

    try:

        user_id = int(
            get_jwt_identity()
        )

        original_project = Project.query.filter_by(
            id=project_id,
            user_id=user_id
        ).first()

        if not original_project:

            return jsonify({

                "success": False,

                "message":
                    "Project not found"

            }), 404

        original_post = Post.query.filter_by(
            project_id=original_project.id
        ).first()

        # ---------------------------------
        # CREATE COPIED PROJECT
        # ---------------------------------

        copied_project = Project(

            user_id=user_id,

            business_profile_id=
                original_project.business_profile_id,

            template_id=
                original_project.template_id,

            title=
                (original_project.title or "Untitled")
                + " Copy",

            content_type=
                original_project.content_type,

            platform=
                original_project.platform,

            language=
                original_project.language,

            tone=
                original_project.tone,

            design_data=
                original_project.design_data,

            status="saved"
        )

        db.session.add(
            copied_project
        )

        db.session.flush()

        # ---------------------------------
        # COPY POST
        # ---------------------------------

        if original_post:

            copied_post = Post(

                user_id=user_id,

                project_id=
                    copied_project.id,

                headline=
                    original_post.headline,

                caption=
                    original_post.caption,

                promotional_text=
                    original_post.promotional_text,

                hashtags=
                    original_post.hashtags,

                call_to_action=
                    original_post.call_to_action,

                reel_idea=
                    original_post.reel_idea,

                reel_script=
                    original_post.reel_script,

                language=
                    original_post.language,

                content_type=
                    original_post.content_type,

                platform=
                    original_post.platform,

                product_image_url=
                    original_post.product_image_url,

                image_url=
                    original_post.image_url,

                download_url=
                    original_post.download_url
            )

            db.session.add(
                copied_post
            )

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Project copied successfully",

            "project_id":
                copied_project.id

        }), 201

    except Exception as e:

        db.session.rollback()

        print(
            "COPY PROJECT ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to copy project"

        }), 500


# =========================================================
# EDIT PROJECT
# =========================================================

@app.route(
    "/api/projects/<int:project_id>",
    methods=["PUT"]
)
@jwt_required()
def edit_project(project_id):

    try:

        user_id = int(
            get_jwt_identity()
        )

        project = Project.query.filter_by(
            id=project_id,
            user_id=user_id
        ).first()

        if not project:

            return jsonify({

                "success": False,

                "message":
                    "Project not found"

            }), 404

        post = Post.query.filter_by(
            project_id=project.id
        ).first()

        if not post:

            return jsonify({

                "success": False,

                "message":
                    "Post not found"

            }), 404

        data = request.get_json() or {}

        # ---------------------------------
        # PROJECT DATA
        # ---------------------------------

        if "title" in data:

            project.title = (
                data.get("title")
                or project.title
            )

        if "content_type" in data:

            project.content_type = (
                data.get("content_type")
                or project.content_type
            )

        if "platform" in data:

            project.platform = (
                data.get("platform")
                or project.platform
            )

        if "language" in data:

            project.language = (
                data.get("language")
                or project.language
            )

        if "tone" in data:

            project.tone = (
                data.get("tone")
                or project.tone
            )

        # ---------------------------------
        # POST DATA
        # ---------------------------------

        if "headline" in data:

            post.headline = data.get(
                "headline"
            )

        if "caption" in data:

            post.caption = data.get(
                "caption"
            )

            post.promotional_text = data.get(
                "caption"
            )

        if "hashtags" in data:

            post.hashtags = data.get(
                "hashtags"
            )

        if "cta" in data:

            post.call_to_action = data.get(
                "cta"
            )

        post.updated_at = datetime.utcnow()

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Project updated successfully"

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "EDIT PROJECT ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to update project"

        }), 500


# Sample AI marketing ideas categorized by business type
BUSINESS_IDEAS = {
    "Fashion & Clothing": [
        "💡 Share a quick styling tip on how to pair your latest collection items for an effortless casual look.",
        "✨ Run a 'Flash Sale' spotlight on your best-selling outfit of the week to drive instant engagement.",
        "👗 Post a 'Behind the Scenes' peek of how you curate fabrics for your boutique customers."
    ],
    "Food & Restaurant": [
        "🍔 Feature your 'Dish of the Day' with a mouth-watering description and a limited-time discount.",
        "☕ Share a morning greeting post highlighting your freshly brewed specials or secret recipe tip.",
        "🍰 Run a weekend poll asking customers to vote for their favorite dessert on your menu."
    ],
    "default": [
        "🚀 Share a useful industry tip or special offer with your customers today to build trust.",
        "⭐ Highlight a customer review or success story to boost your brand credibility.",
        "🎯 Post an engaging question related to your niche to drive comments and user interaction."
    ]
}



@app.route("/api/today-idea", methods=["GET"])
@jwt_required()
def get_today_idea():
  try:
    user_id = int(get_jwt_identity())

    profile = BusinessProfile.query.filter_by(user_id=user_id).first()

    if not profile:
      return (
          jsonify(
              {"success": False, "message": "Please create business profile first"}
          ),
          400,
      )

    category = profile.category or "General Business"
    business_name = profile.business_name or ""
    description = profile.description or ""

    today = datetime.utcnow().date()

    # 1. Check if today's idea already exists in database
    existing_idea = DailyContentIdea.query.filter_by(
        user_id=user_id, usage_date=today
    ).first()

    if existing_idea:
      # Agar pehle se bna hua hai toh wahi utha kar bhej do
      encoded_query = quote_plus(
          f"{category} {existing_idea.idea} trending video"
      )
      target_url = getattr(
          existing_idea,
          "target_url",
          f"https://www.youtube.com/results?search_query={encoded_query}",
      )
      platform = getattr(existing_idea, "platform", "youtube")

      return (
          jsonify({
              "success": True,
              "message": "Today's idea loaded from database",
              "idea": {
                  "id": existing_idea.id,
                  "idea": existing_idea.idea,
                  "content_type": existing_idea.content_type,
                  "language": existing_idea.language,
                  "category": category,
                  "platform": platform,
                  "target_url": target_url,
              },
          }),
          200,
      )

    # 2. Generate new idea using Gemini AI if not exists for today
    ai_prompt = f"""
You are a social media marketing expert.
Create ONE useful and realistic social media content idea for a business.

BUSINESS NAME: {business_name}
BUSINESS CATEGORY: {category}
BUSINESS DESCRIPTION: {description}

Return ONLY valid JSON with no extra text:
{{
    "idea": "A short and catchy description of the content idea for today",
    "content_type": "e.g., Short-form Video, Reel, Product Showcase",
    "platform": "youtube", 
    "search_query": "A keyword query to search this video or post on YouTube or Instagram"
}}
Note: 'platform' must be one of: youtube, instagram, facebook.
"""

    response = ai_client.models.generate_content(
        model="gemini-3.6-flash", contents=ai_prompt
    )

    raw_text = (response.text or "").strip()

    # Clean JSON markdown if any
    if "```json" in raw_text:
      raw_text = raw_text.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in raw_text:
      raw_text = raw_text.split("```", 1)[1].split("```", 1)[0].strip()

    import json

    try:
      generated = json.loads(raw_text)
    except Exception:
      generated = {
          "idea": f"Create an engaging post about your {category} products.",
          "content_type": "Video Reel",
          "platform": "youtube",
          "search_query": f"{category} business ideas",
      }

    idea_text = generated.get("idea", "Create an engaging post today.")
    content_type = generated.get("content_type", "Video")
    platform = generated.get("platform", "youtube").lower()
    search_query = generated.get("search_query", f"{category} ideas")

    encoded_query = quote_plus(search_query)

    # Platform ke hisaab se direct target URL banana
    if platform == "youtube":
      target_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    elif platform == "instagram":
      target_url = (
          f"https://www.google.com/search?q=site%3Ainstagram.com+{encoded_query}"
      )
    else:
      target_url = (
          f"https://www.google.com/search?q=site%3Afacebook.com+{encoded_query}"
      )

    # 3. Save to Database (Ensure your model has platform & target_url columns, or handle them accordingly)
    new_idea = DailyContentIdea(
        user_id=user_id,
        business_profile_id=profile.id,
        idea=idea_text,
        content_type=content_type,
        language="English",
        usage_date=today,
        platform=platform,       # <--- Yeh add karein
        target_url=target_url,
    )

    db.session.add(new_idea)
    db.session.commit()

    return (
        jsonify({
            "success": True,
            "message": "Today's content idea generated successfully",
            "idea": {
                "id": new_idea.id,
                "category": category,
                "idea": idea_text,
                "content_type": content_type,
                "language": "English",
                "platform": platform,
                "target_url": target_url,
            },
        }),
        200,
    )

  except Exception as e:
    db.session.rollback()
    print("TODAY IDEA ERROR:", str(e))
    return (
        jsonify({
            "success": False,
            "message": "Unable to generate today's content idea",
            "error": str(e),
        }),
        500,
    )


# =========================================================
# SUBSCRIPTION CONFIGURATION
# =========================================================

GOOGLE_PLAY_PACKAGE_NAME = os.getenv(
    "GOOGLE_PLAY_PACKAGE_NAME",
    ""
)

GOOGLE_PLAY_SERVICE_ACCOUNT_FILE = os.getenv(
    "GOOGLE_PLAY_SERVICE_ACCOUNT_FILE",
    "google-play-service-account.json"
)

# Google Play product IDs.
# In Google Play Console these same IDs must be created.
GOOGLE_PLAY_PRODUCT_IDS = {
    "Pro": os.getenv(
        "GOOGLE_PLAY_PRO_PRODUCT_ID",
        "pro_monthly"
    ),
    "Business": os.getenv(
        "GOOGLE_PLAY_BUSINESS_PRODUCT_ID",
        "business_monthly"
    ),
}

# =========================================================
# SUBSCRIPTION PLAN SEEDING
# =========================================================
@app.cli.command("seed-plans")
def seed_subscription_plans_cli():
    seed_subscription_plans_cli()
    """
    Creates the three plans only if they do not already exist.

    Existing plans are NOT deleted or duplicated.
    """

    plans = [
        {
            "name": "Free",
            "ai_generation_limit": 10,
            "premium_templates": False,
            "advertisements": True,
            "hd_downloads": False,
            "brand_kit_access": False,
            "multiple_business_profiles": False,
            "multiple_brand_kits": False,
            "advanced_ai_options": False,
            "advanced_marketing_tools": False,
            "watermark": True,
            "price": 0.0,
        },
        {
            "name": "Pro",
            "ai_generation_limit": 50,
            "premium_templates": True,
            "advertisements": False,
            "hd_downloads": True,
            "brand_kit_access": True,
            "multiple_business_profiles": False,
            "multiple_brand_kits": False,
            "advanced_ai_options": True,
            "advanced_marketing_tools": False,
            "watermark": False,
            "price": 0.0,
        },
        {
            "name": "Business",
            "ai_generation_limit": 200,
            "premium_templates": True,
            "advertisements": False,
            "hd_downloads": True,
            "brand_kit_access": True,
            "multiple_business_profiles": True,
            "multiple_brand_kits": True,
            "advanced_ai_options": True,
            "advanced_marketing_tools": True,
            "watermark": False,
            "price": 0.0,
        },
    ]

    for plan_data in plans:

        existing_plan = SubscriptionPlan.query.filter_by(
            name=plan_data["name"]
        ).first()

        if existing_plan:
            continue

        plan = SubscriptionPlan(
            name=plan_data["name"],
            ai_generation_limit=plan_data[
                "ai_generation_limit"
            ],
            premium_templates=plan_data[
                "premium_templates"
            ],
            advertisements=plan_data[
                "advertisements"
            ],
            hd_downloads=plan_data[
                "hd_downloads"
            ],
            brand_kit_access=plan_data[
                "brand_kit_access"
            ],
            multiple_business_profiles=plan_data[
                "multiple_business_profiles"
            ],
            multiple_brand_kits=plan_data[
                "multiple_brand_kits"
            ],
            advanced_ai_options=plan_data[
                "advanced_ai_options"
            ],
            advanced_marketing_tools=plan_data[
                "advanced_marketing_tools"
            ],
            watermark=plan_data[
                "watermark"
            ],
            price=plan_data["price"],
        )

        db.session.add(plan)

    db.session.commit()


# =========================================================
# GOOGLE PLAY VERIFICATION HELPER
# =========================================================

def get_google_play_service():

    if not GOOGLE_PLAY_PACKAGE_NAME:
        raise Exception(
            "GOOGLE_PLAY_PACKAGE_NAME is not configured"
        )

    if not os.path.exists(
        GOOGLE_PLAY_SERVICE_ACCOUNT_FILE
    ):
        raise Exception(
            "Google Play service account file not found"
        )

    credentials = (
        service_account.Credentials.from_service_account_file(
            GOOGLE_PLAY_SERVICE_ACCOUNT_FILE,
            scopes=[
                "https://www.googleapis.com/auth/"
                "androidpublisher"
            ],
        )
    )

    service = build(
        "androidpublisher",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    return service


# =========================================================
# VERIFY GOOGLE PLAY SUBSCRIPTION
# =========================================================

def verify_google_play_subscription(
    product_id,
    purchase_token
):

    if not product_id:
        raise Exception(
            "Google Play product ID is required"
        )

    if not purchase_token:
        raise Exception(
            "Google Play purchase token is required"
        )

    service = get_google_play_service()

    result = (
        service
        .purchases()
        .subscriptions()
        .get(
            packageName=GOOGLE_PLAY_PACKAGE_NAME,
            subscriptionId=product_id,
            token=purchase_token,
        )
        .execute()
    )

    return result

# =========================================================
# SUBSCRIPTION SERIALIZER
# =========================================================

def subscription_plan_to_dict(plan):

    return {
        "id": plan.id,
        "name": plan.name,
        "ai_generation_limit":
            plan.ai_generation_limit,
        "premium_templates":
            bool(plan.premium_templates),
        "advertisements":
            bool(plan.advertisements),
        "hd_downloads":
            bool(plan.hd_downloads),
        "brand_kit_access":
            bool(plan.brand_kit_access),
        "multiple_business_profiles":
            bool(plan.multiple_business_profiles),
        "multiple_brand_kits":
            bool(plan.multiple_brand_kits),
        "advanced_ai_options":
            bool(plan.advanced_ai_options),
        "advanced_marketing_tools":
            bool(plan.advanced_marketing_tools),
        "watermark":
            bool(plan.watermark),
        "price":
            float(plan.price or 0),
        "google_product_id":
            GOOGLE_PLAY_PRODUCT_IDS.get(
                plan.name
            ),
    }

# =========================================================
# GET SUBSCRIPTION PLANS
# =========================================================

@app.route(
    "/api/subscription/plans",
    methods=["GET"]
)
@jwt_required()
def get_subscription_plans():

    try:

        plans = (
            SubscriptionPlan.query
            .order_by(
                SubscriptionPlan.id.asc()
            )
            .all()
        )

        return jsonify({
            "success": True,
            "plans": [
                subscription_plan_to_dict(plan)
                for plan in plans
            ]
        }), 200

    except Exception as e:

        print(
            "SUBSCRIPTION PLANS ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to load subscription plans"
        }), 500
 # =========================================================
# GET CURRENT USER SUBSCRIPTION
# =========================================================

@app.route(
    "/api/subscription",
    methods=["GET"]
)
@jwt_required()
def get_current_subscription():

    try:

        user_id = int(
            get_jwt_identity()
        )

        free_plan = SubscriptionPlan.query.filter_by(
            name="Free"
        ).first()

        if not free_plan:

            return jsonify({
                "success": False,
                "message":
                    "Free subscription plan not found"
            }), 500

        subscription = (
            Subscription.query
            .filter_by(user_id=user_id)
            .order_by(
                Subscription.id.desc()
            )
            .first()
        )

        # -------------------------------------------------
        # If user has no subscription,
        # automatically give Free plan.
        # -------------------------------------------------

        if not subscription:

            subscription = Subscription(
                user_id=user_id,
                plan_id=free_plan.id,
                status="active",
                start_date=datetime.utcnow(),
                end_date=None,
                google_purchase_token=None,
            )

            db.session.add(subscription)
            db.session.commit()

        # -------------------------------------------------
        # Expired paid subscription
        # -------------------------------------------------

        if (
            subscription.end_date
            and subscription.end_date < datetime.utcnow()
            and subscription.status == "active"
        ):

            subscription.status = "expired"

            db.session.commit()

        plan = SubscriptionPlan.query.filter_by(
            id=subscription.plan_id
        ).first()

        if not plan:

            plan = free_plan

        is_active = (
            subscription.status == "active"
            and (
                subscription.end_date is None
                or subscription.end_date >= datetime.utcnow()
            )
        )

        return jsonify({

            "success": True,

            "subscription": {

                "id": subscription.id,

                "status":
                    "active"
                    if is_active
                    else subscription.status,

                "start_date":
                    subscription.start_date.isoformat()
                    if subscription.start_date
                    else None,

                "end_date":
                    subscription.end_date.isoformat()
                    if subscription.end_date
                    else None,

                "plan":
                    subscription_plan_to_dict(
                        plan
                    ),
            }

        }), 200

    except Exception as e:

        print(
            "CURRENT SUBSCRIPTION ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to load subscription"
        }), 500

# =========================================================
# VERIFY + ACTIVATE GOOGLE PLAY SUBSCRIPTION
# =========================================================

@app.route(
    "/api/subscription/verify",
    methods=["POST"]
)
@jwt_required()
def verify_subscription():

    try:

        user_id = int(
            get_jwt_identity()
        )

        data = request.get_json() or {}

        plan_name = (
            data.get("plan_name") or ""
        ).strip()

        purchase_token = (
            data.get("purchase_token") or ""
        ).strip()

        if not plan_name:

            return jsonify({
                "success": False,
                "message":
                    "Plan name is required"
            }), 400

        if not purchase_token:

            return jsonify({
                "success": False,
                "message":
                    "Purchase token is required"
            }), 400

        if plan_name not in [
            "Pro",
            "Business"
        ]:

            return jsonify({
                "success": False,
                "message":
                    "Invalid paid subscription plan"
            }), 400

        plan = SubscriptionPlan.query.filter_by(
            name=plan_name
        ).first()

        if not plan:

            return jsonify({
                "success": False,
                "message":
                    "Subscription plan not found"
            }), 404

        product_id = GOOGLE_PLAY_PRODUCT_IDS.get(
            plan_name
        )

        if not product_id:

            return jsonify({
                "success": False,
                "message":
                    "Google Play product ID is not configured"
            }), 500

        # -------------------------------------------------
        # VERIFY PURCHASE DIRECTLY WITH GOOGLE
        # -------------------------------------------------

        google_purchase = (
            verify_google_play_subscription(
                product_id=product_id,
                purchase_token=purchase_token,
            )
        )

        # Google subscription purchase state:
        #
        # 0 = purchased
        # 1 = canceled
        #
        # Different Google API responses may also contain
        # expiry information.

        purchase_state = google_purchase.get(
            "paymentState"
        )

        expiry_time_millis = google_purchase.get(
            "expiryTimeMillis"
        )

        auto_renewing = google_purchase.get(
            "autoRenewing",
            False
        )

        # -------------------------------------------------
        # Purchase must have valid payment state.
        # -------------------------------------------------

        if (
            purchase_state is not None
            and str(purchase_state) != "1"
        ):

            return jsonify({
                "success": False,
                "message":
                    "Google Play purchase is not completed",
                "google_purchase":
                    google_purchase,
            }), 400

        # -------------------------------------------------
        # Calculate expiry
        # -------------------------------------------------

        end_date = None

        if expiry_time_millis:

            try:

                expiry_seconds = (
                    int(expiry_time_millis)
                    / 1000
                )

                end_date = datetime.utcfromtimestamp(
                    expiry_seconds
                )

            except Exception:

                end_date = None

        # -------------------------------------------------
        # Find existing subscription
        # -------------------------------------------------

        subscription = (
            Subscription.query
            .filter_by(user_id=user_id)
            .order_by(
                Subscription.id.desc()
            )
            .first()
        )

        if not subscription:

            subscription = Subscription(
                user_id=user_id
            )

            db.session.add(subscription)

        subscription.plan_id = plan.id
        subscription.status = "active"
        subscription.start_date = (
            subscription.start_date
            or datetime.utcnow()
        )
        subscription.end_date = end_date
        subscription.google_purchase_token = (
            purchase_token
        )

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Subscription verified successfully",

            "subscription": {

                "id": subscription.id,

                "status":
                    subscription.status,

                "start_date":
                    subscription.start_date.isoformat()
                    if subscription.start_date
                    else None,

                "end_date":
                    subscription.end_date.isoformat()
                    if subscription.end_date
                    else None,

                "auto_renewing":
                    bool(auto_renewing),

                "plan":
                    subscription_plan_to_dict(
                        plan
                    ),
            }

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "SUBSCRIPTION VERIFY ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to verify subscription",
            "error": str(e),
        }), 500

# =========================================================
# RESTORE SUBSCRIPTION
# =========================================================

@app.route(
    "/api/subscription/restore",
    methods=["POST"]
)
@jwt_required()
def restore_subscription():

    try:

        user_id = int(
            get_jwt_identity()
        )

        data = request.get_json() or {}

        plan_name = (
            data.get("plan_name") or ""
        ).strip()

        purchase_token = (
            data.get("purchase_token") or ""
        ).strip()

        if not plan_name or not purchase_token:

            return jsonify({
                "success": False,
                "message":
                    "Plan name and purchase token are required"
            }), 400

        if plan_name not in [
            "Pro",
            "Business"
        ]:

            return jsonify({
                "success": False,
                "message":
                    "Invalid subscription plan"
            }), 400

        plan = SubscriptionPlan.query.filter_by(
            name=plan_name
        ).first()

        if not plan:

            return jsonify({
                "success": False,
                "message":
                    "Subscription plan not found"
            }), 404

        product_id = GOOGLE_PLAY_PRODUCT_IDS.get(
            plan_name
        )

        google_purchase = (
            verify_google_play_subscription(
                product_id,
                purchase_token
            )
        )

        expiry_time_millis = (
            google_purchase.get(
                "expiryTimeMillis"
            )
        )

        if not expiry_time_millis:

            return jsonify({
                "success": False,
                "message":
                    "No valid subscription expiry found"
            }), 400

        end_date = datetime.utcfromtimestamp(
            int(expiry_time_millis) / 1000
        )

        if end_date < datetime.utcnow():

            return jsonify({
                "success": False,
                "message":
                    "Subscription has expired"
            }), 400

        subscription = (
            Subscription.query
            .filter_by(user_id=user_id)
            .order_by(
                Subscription.id.desc()
            )
            .first()
        )

        if not subscription:

            subscription = Subscription(
                user_id=user_id
            )

            db.session.add(subscription)

        subscription.plan_id = plan.id
        subscription.status = "active"
        subscription.start_date = (
            subscription.start_date
            or datetime.utcnow()
        )
        subscription.end_date = end_date
        subscription.google_purchase_token = (
            purchase_token
        )

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Subscription restored successfully",

            "subscription": {

                "id": subscription.id,

                "status":
                    subscription.status,

                "start_date":
                    subscription.start_date.isoformat()
                    if subscription.start_date
                    else None,

                "end_date":
                    subscription.end_date.isoformat()
                    if subscription.end_date
                    else None,

                "plan":
                    subscription_plan_to_dict(
                        plan
                    ),
            }

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "SUBSCRIPTION RESTORE ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to restore subscription",
            "error": str(e),
        }), 500
 # =========================================================
# CANCEL SUBSCRIPTION IN OUR DATABASE
# =========================================================

@app.route(
    "/api/subscription/cancel",
    methods=["POST"]
)
@jwt_required()
def cancel_subscription():

    try:

        user_id = int(
            get_jwt_identity()
        )

        subscription = (
            Subscription.query
            .filter_by(
                user_id=user_id,
                status="active"
            )
            .order_by(
                Subscription.id.desc()
            )
            .first()
        )

        if not subscription:

            return jsonify({
                "success": False,
                "message":
                    "No active subscription found"
            }), 404

        # -------------------------------------------------
        # Important:
        # This marks our application's subscription state.
        # Actual Google Play recurring billing cancellation
        # is handled by Google Play.
        # -------------------------------------------------

        subscription.status = "cancelled"

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Subscription marked as cancelled",

            "subscription": {

                "id":
                    subscription.id,

                "status":
                    subscription.status,

                "end_date":
                    subscription.end_date.isoformat()
                    if subscription.end_date
                    else None,
            }

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "SUBSCRIPTION CANCEL ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to cancel subscription"
        }), 500


@app.route("/api/profile", methods=["GET"])
@jwt_required()
def get_user_profile():
    try:
        user_id = int(get_jwt_identity())
        user = User.query.filter_by(id=user_id).first()

        if not user:
            return jsonify({
                "success": False,
                "message": "User not found"
            }), 404

        # AI Usage ki details yahan fetch karein
        usage_status = check_ai_generation_limit(user_id)

        return jsonify({
            "success": True,
            "user": {
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role,
                "status": user.status,
            },
            # Yeh usage data Flutter app ko bhejega
            "usage": usage_status 
        }), 200

    except Exception as e:
        print("PROFILE ERROR:", str(e))
        return jsonify({
            "success": False,
            "message": "Unable to load profile"
        }), 500

        # =========================================================
# ADMIN DASHBOARD
# =========================================================

from sqlalchemy import func


# =========================================================
# ADMIN AUTHORIZATION HELPER
# =========================================================

def admin_required():
    """
    Check whether the currently logged-in user is an admin.
    Returns:
        (user, None) when authorized
        (None, response) when unauthorized
    """

    try:
        user_id = int(get_jwt_identity())
    except Exception:
        return None, (
            jsonify({
                "success": False,
                "message": "Invalid user identity"
            }),
            401
        )

    user = User.query.get(user_id)

    if not user:
        return None, (
            jsonify({
                "success": False,
                "message": "User not found"
            }),
            404
        )

    if user.role != "admin":
        return None, (
            jsonify({
                "success": False,
                "message": "Admin access required"
            }),
            403
        )

    if user.status != "active":
        return None, (
            jsonify({
                "success": False,
                "message": "Admin account is not active"
            }),
            403
        )

    return user, None


# =========================================================
# ADMIN DASHBOARD OVERVIEW
# =========================================================

@app.route(
    "/api/admin/dashboard",
    methods=["GET"]
)
@jwt_required()
def admin_dashboard():

    try:

        admin, error = admin_required()

        if error:
            return error

        # -------------------------------------------------
        # USERS
        # -------------------------------------------------

        total_users = User.query.filter(
            User.role == "user"
        ).count()

        active_users = User.query.filter(
            User.role == "user",
            User.status == "active"
        ).count()

        blocked_users = User.query.filter(
            User.role == "user",
            User.status != "active"
        ).count()

        # -------------------------------------------------
        # SUBSCRIPTIONS
        # -------------------------------------------------

        free_users = 0
        premium_users = 0

        users = User.query.filter(
            User.role == "user"
        ).all()

        for user in users:

            subscription = (
                Subscription.query
                .filter_by(
                    user_id=user.id
                )
                .order_by(
                    Subscription.id.desc()
                )
                .first()
            )

            is_premium = False

            if subscription:

                if (
                    subscription.status == "active"
                    and (
                        subscription.end_date is None
                        or subscription.end_date >= datetime.utcnow()
                    )
                ):

                    plan = SubscriptionPlan.query.get(
                        subscription.plan_id
                    )

                    if plan and plan.name != "Free":
                        is_premium = True

            if is_premium:
                premium_users += 1
            else:
                free_users += 1

        # -------------------------------------------------
        # POSTS
        # -------------------------------------------------

        total_posts = 0

        try:
            total_posts = Post.query.count()
        except Exception:
            total_posts = 0

        # -------------------------------------------------
        # AI USAGE
        # -------------------------------------------------

        total_ai_generations = db.session.query(
            func.coalesce(
                func.sum(
                    AIUsage.generation_count
                ),
                0
            )
        ).scalar()

        total_ai_generations = int(
            total_ai_generations or 0
        )

        # -------------------------------------------------
        # SUBSCRIPTION STATISTICS
        # -------------------------------------------------

        active_subscriptions = Subscription.query.filter(
            Subscription.status == "active"
        ).count()

        expired_subscriptions = Subscription.query.filter(
            Subscription.status != "active"
        ).count()

        # -------------------------------------------------
        # REVENUE
        # -------------------------------------------------

        estimated_revenue = 0.0

        active_subscriptions_list = (
            Subscription.query
            .filter_by(status="active")
            .all()
        )

        for subscription in active_subscriptions_list:

            plan = SubscriptionPlan.query.get(
                subscription.plan_id
            )

            if plan:
                estimated_revenue += float(
                    plan.price or 0
                )

        # -------------------------------------------------
        # TEMPLATE STATISTICS
        # -------------------------------------------------

        total_templates = Template.query.count()

        active_templates = Template.query.filter_by(
            is_active=True
        ).count()

        free_templates = Template.query.filter_by(
            is_premium=False,
            is_active=True
        ).count()

        premium_templates = Template.query.filter_by(
            is_premium=True,
            is_active=True
        ).count()

        # -------------------------------------------------
        # CATEGORY STATISTICS
        # -------------------------------------------------

        total_categories = Category.query.count()

        active_categories = Category.query.filter_by(
            is_active=True
        ).count()

        # -------------------------------------------------
        # REPORTS
        # -------------------------------------------------

        pending_reports = Report.query.filter_by(
            status="pending"
        ).count()

        total_reports = Report.query.count()

        # -------------------------------------------------
        # MOST USED TEMPLATES
        # -------------------------------------------------

        most_used_templates = []

        try:

            template_usage = (
                db.session.query(
                    Post.template_id,
                    func.count(
                        Post.id
                    ).label("usage_count")
                )
                .filter(
                    Post.template_id.isnot(None)
                )
                .group_by(
                    Post.template_id
                )
                .order_by(
                    func.count(
                        Post.id
                    ).desc()
                )
                .limit(5)
                .all()
            )

            for row in template_usage:

                template = Template.query.get(
                    row.template_id
                )

                if template:

                    most_used_templates.append({
                        "id": template.id,
                        "name": template.name,
                        "preview_url":
                            template.preview_url,
                        "usage_count":
                            int(row.usage_count)
                    })

        except Exception:
            most_used_templates = []

        # -------------------------------------------------
        # RECENT USERS
        # -------------------------------------------------

        recent_users = []

        recent_user_list = (
            User.query
            .filter(
                User.role == "user"
            )
            .order_by(
                User.id.desc()
            )
            .limit(8)
            .all()
        )

        for user in recent_user_list:

            recent_users.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "status": user.status,
                "role": user.role
            })

        # -------------------------------------------------
        # FINAL RESPONSE
        # -------------------------------------------------

        return jsonify({

            "success": True,

            "admin": {
                "id": admin.id,
                "name": admin.name,
                "email": admin.email
            },

            "statistics": {

                "users": {
                    "total": total_users,
                    "active": active_users,
                    "blocked": blocked_users,
                    "free": free_users,
                    "premium": premium_users
                },

                "posts": {
                    "total": total_posts
                },

                "ai": {
                    "total_generations":
                        total_ai_generations
                },

                "templates": {
                    "total": total_templates,
                    "active": active_templates,
                    "free": free_templates,
                    "premium": premium_templates
                },

                "categories": {
                    "total": total_categories,
                    "active": active_categories
                },

                "subscriptions": {
                    "active":
                        active_subscriptions,
                    "expired":
                        expired_subscriptions
                },

                "reports": {
                    "total": total_reports,
                    "pending":
                        pending_reports
                },

                "revenue": {
                    "estimated":
                        round(
                            estimated_revenue,
                            2
                        )
                }
            },

            "most_used_templates":
                most_used_templates,

            "recent_users":
                recent_users

        }), 200

    except Exception as e:

        print(
            "ADMIN DASHBOARD ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to load admin dashboard",

            "error": str(e)

        }), 500


# =========================================================
# ADMIN USER MANAGEMENT
# =========================================================

@app.route(
    "/api/admin/users",
    methods=["GET"]
)
@jwt_required()
def admin_get_users():

    try:

        admin, error = admin_required()

        if error:
            return error

        users = (
            User.query
            .filter(
                User.role == "user"
            )
            .order_by(
                User.id.desc()
            )
            .all()
        )

        result = []

        for user in users:

            result.append({

                "id": user.id,
                "name": user.name,
                "email": user.email,
                "status": user.status,
                "role": user.role

            })

        return jsonify({

            "success": True,
            "users": result

        }), 200

    except Exception as e:

        print(
            "ADMIN USERS ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to load users"

        }), 500


# =========================================================
# BLOCK / UNBLOCK USER
# =========================================================

@app.route(
    "/api/admin/users/<int:user_id>/status",
    methods=["PUT"]
)
@jwt_required()
def admin_change_user_status(user_id):

    try:

        admin, error = admin_required()

        if error:
            return error

        user = User.query.get(user_id)

        if not user:

            return jsonify({

                "success": False,
                "message": "User not found"

            }), 404

        if user.role == "admin":

            return jsonify({

                "success": False,
                "message":
                    "Admin account cannot be blocked"

            }), 403

        data = request.get_json() or {}

        new_status = (
            data.get("status") or ""
        ).strip().lower()

        if new_status not in [
            "active",
            "blocked"
        ]:

            return jsonify({

                "success": False,
                "message":
                    "Status must be active or blocked"

            }), 400

        user.status = new_status

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "User status updated successfully",

            "user": {

                "id": user.id,
                "name": user.name,
                "email": user.email,
                "status": user.status

            }

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "ADMIN USER STATUS ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to update user status"

        }), 500


# =========================================================
# ADMIN TEMPLATES
# =========================================================

@app.route(
    "/api/admin/templates",
    methods=["GET"]
)
@jwt_required()
def admin_get_templates():

    try:

        admin, error = admin_required()

        if error:
            return error

        templates = (
            Template.query
            .order_by(
                Template.id.desc()
            )
            .all()
        )

        result = []

        for template in templates:

            category_name = ""

            if template.category_id:

                category = Category.query.get(
                    template.category_id
                )

                if category:
                    category_name = category.name

            result.append({

                "id": template.id,

                "name":
                    template.name,

                "category_id":
                    template.category_id,

                "category_name":
                    category_name,

                "preview_url":
                    template.preview_url,

                "template_data":
                    template.template_data,

                "is_premium":
                    bool(template.is_premium),

                "is_active":
                    bool(template.is_active)

            })

        return jsonify({

            "success": True,
            "templates": result

        }), 200

    except Exception as e:

        print(
            "ADMIN TEMPLATES ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to load templates"

        }), 500

# =========================================================
# ADMIN CREATE TEMPLATE
# =========================================================

@app.route(
    "/api/admin/templates",
    methods=["POST"]
)
@jwt_required()
def admin_create_template():

    try:

        # -------------------------------------------------
        # ADMIN AUTHORIZATION
        # -------------------------------------------------

        admin, error = admin_required()

        if error:
            return error

        # -------------------------------------------------
        # FORM DATA
        # -------------------------------------------------

        name = (
            request.form.get("name") or ""
        ).strip()

        category_id = request.form.get(
            "category_id"
        )

        template_data = (
            request.form.get("template_data")
            or "{}"
        )

        is_premium = (
            request.form.get(
                "is_premium",
                "false"
            ).lower() == "true"
        )

        # -------------------------------------------------
        # VALIDATION
        # -------------------------------------------------

        if not name:

            return jsonify({
                "success": False,
                "message":
                    "Template name is required"
            }), 400

        if not category_id:

            return jsonify({
                "success": False,
                "message":
                    "Category is required"
            }), 400

        try:

            category_id = int(
                category_id
            )

        except (TypeError, ValueError):

            return jsonify({
                "success": False,
                "message":
                    "Invalid category_id"
            }), 400

        # -------------------------------------------------
        # CHECK CATEGORY
        # -------------------------------------------------

        category = Category.query.get(
            category_id
        )

        if not category:

            return jsonify({
                "success": False,
                "message":
                    "Category not found"
            }), 404

        # -------------------------------------------------
        # CHECK TEMPLATE DATA
        # -------------------------------------------------

        try:

            json.loads(template_data)

        except Exception:

            return jsonify({
                "success": False,
                "message":
                    "Invalid template_data JSON"
            }), 400

        # -------------------------------------------------
        # TEMPLATE IMAGE / PREVIEW
        # -------------------------------------------------

        preview_file = request.files.get(
            "preview"
        )

        preview_url = None

        if preview_file:

            if not preview_file.filename:

                return jsonify({
                    "success": False,
                    "message":
                        "Invalid preview image"
                }), 400

            # ---------------------------------------------
            # CLOUDINARY UPLOAD
            # ---------------------------------------------

            upload_result = cloudinary.uploader.upload(
                preview_file,
                folder="ai_business_post_maker/templates"
            )

            preview_url = upload_result.get(
                "secure_url"
            )

            if not preview_url:

                return jsonify({
                    "success": False,
                    "message":
                        "Template image upload failed"
                }), 500

        # -------------------------------------------------
        # CREATE TEMPLATE
        # -------------------------------------------------

        template = Template(

            name=name,

            category_id=category_id,

            preview_url=preview_url,

            template_data=template_data,

            is_premium=is_premium,

            is_active=True
        )

        db.session.add(
            template
        )

        db.session.commit()

        # -------------------------------------------------
        # RESPONSE
        # -------------------------------------------------

        return jsonify({

            "success": True,

            "message":
                "Template created successfully",

            "template": {

                "id":
                    template.id,

                "name":
                    template.name,

                "category_id":
                    template.category_id,

                "category_name":
                    category.name,

                "preview_url":
                    template.preview_url,

                "template_data":
                    template.template_data,

                "is_premium":
                    bool(
                        template.is_premium
                    ),

                "is_active":
                    bool(
                        template.is_active
                    )
            }

        }), 201

    except Exception as e:

        db.session.rollback()

        print(
            "ADMIN CREATE TEMPLATE ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,

            "message":
                "Unable to create template",

            "error":
                str(e)

        }), 500
# =========================================================
# FREE / PREMIUM TEMPLATE CONTROL
# =========================================================

@app.route(
    "/api/admin/templates/<int:template_id>",
    methods=["PUT"]
)
@jwt_required()
def admin_update_template(template_id):

    try:

        admin, error = admin_required()

        if error:
            return error

        template = Template.query.get(
            template_id
        )

        if not template:

            return jsonify({

                "success": False,
                "message":
                    "Template not found"

            }), 404

        data = request.get_json() or {}

        if "is_premium" in data:

            template.is_premium = bool(
                data.get("is_premium")
            )

        if "is_active" in data:

            template.is_active = bool(
                data.get("is_active")
            )

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Template updated successfully",

            "template": {

                "id": template.id,

                "name": template.name,

                "is_premium":
                    bool(template.is_premium),

                "is_active":
                    bool(template.is_active)

            }

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "ADMIN TEMPLATE UPDATE ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to update template"

        }), 500


# =========================================================
# ADMIN CATEGORIES
# =========================================================

@app.route(
    "/api/admin/categories",
    methods=["GET"]
)
@jwt_required()
def admin_get_categories():

    try:

        admin, error = admin_required()

        if error:
            return error

        categories = (
            Category.query
            .order_by(
                Category.name.asc()
            )
            .all()
        )

        result = []

        for category in categories:

            result.append({

                "id": category.id,

                "name":
                    category.name,

                "description":
                    category.description,

                "is_active":
                    bool(category.is_active)

            })

        return jsonify({

            "success": True,
            "categories": result

        }), 200

    except Exception as e:

        print(
            "ADMIN CATEGORIES ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to load categories"

        }), 500

# =========================================================
# ADMIN ADD CATEGORY
# =========================================================

@app.route(
    "/api/admin/categories",
    methods=["POST"]
)
@jwt_required()
def admin_add_category():
    try:
        admin, error = admin_required()

        if error:
            return error

        data = request.get_json() or {}

        name = (
            data.get("name") or ""
        ).strip()

        description = (
            data.get("description") or ""
        ).strip()

        if not name:
            return jsonify({
                "success": False,
                "message": "Category name is required"
            }), 400

        existing = Category.query.filter(
            db.func.lower(Category.name) == name.lower()
        ).first()

        if existing:
            return jsonify({
                "success": False,
                "message": "Category already exists"
            }), 409

        category = Category(
            name=name,
            description=description,
            is_active=True
        )

        db.session.add(category)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Category created successfully",
            "category": {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "is_active": bool(category.is_active)
            }
        }), 201

    except Exception as e:
        db.session.rollback()

        print(
            "ADMIN ADD CATEGORY ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message": "Unable to create category"
        }), 500

# =========================================================
# ADMIN CATEGORY STATUS
# =========================================================

@app.route(
    "/api/admin/categories/<int:category_id>/status",
    methods=["PUT"]
)
@jwt_required()
def admin_change_category_status(category_id):
    try:
        admin, error = admin_required()

        if error:
            return error

        category = Category.query.get(category_id)

        if not category:
            return jsonify({
                "success": False,
                "message": "Category not found"
            }), 404

        data = request.get_json() or {}

        new_status = (
            data.get("status") or ""
        ).strip().lower()

        if new_status not in [
            "active",
            "inactive"
        ]:
            return jsonify({
                "success": False,
                "message":
                    "Status must be active or inactive"
            }), 400

        category.is_active = (
            new_status == "active"
        )

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Category status updated successfully",
            "category": {
                "id": category.id,
                "name": category.name,
                "description": category.description,
                "is_active": bool(category.is_active)
            }
        }), 200

    except Exception as e:
        db.session.rollback()

        print(
            "ADMIN CATEGORY STATUS ERROR:",
            str(e)
        )

        return jsonify({
            "success": False,
            "message":
                "Unable to update category status"
        }), 500

# =========================================================
# ADMIN SUBSCRIPTION PLANS
# =========================================================

@app.route(
    "/api/admin/subscription-plans",
    methods=["GET"]
)
@jwt_required()
def admin_get_subscription_plans():

    try:

        admin, error = admin_required()

        if error:
            return error

        plans = (
            SubscriptionPlan.query
            .order_by(
                SubscriptionPlan.id.asc()
            )
            .all()
        )

        result = []

        for plan in plans:

            result.append({

                "id": plan.id,

                "name":
                    plan.name,

                "price":
                    float(plan.price or 0),

                "ai_generation_limit":
                    plan.ai_generation_limit,

                "premium_templates":
                    bool(plan.premium_templates),

                "advertisements":
                    bool(plan.advertisements),

                "hd_downloads":
                    bool(plan.hd_downloads),

                "brand_kit_access":
                    bool(plan.brand_kit_access),

                "multiple_business_profiles":
                    bool(plan.multiple_business_profiles),

                "multiple_brand_kits":
                    bool(plan.multiple_brand_kits),

                "advanced_ai_options":
                    bool(plan.advanced_ai_options),

                "advanced_marketing_tools":
                    bool(plan.advanced_marketing_tools),

                "watermark":
                    bool(plan.watermark)

            })

        return jsonify({

            "success": True,
            "plans": result

        }), 200

    except Exception as e:

        print(
            "ADMIN PLANS ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to load subscription plans"

        }), 500

# =========================================================
# ADMIN REPORTS
# =========================================================

@app.route(
    "/api/admin/reports",
    methods=["GET"]
)
@jwt_required()
def admin_get_reports():

    try:

        admin, error = admin_required()

        if error:
            return error

        reports = (
            Report.query
            .order_by(
                Report.id.desc()
            )
            .limit(50)
            .all()
        )

        result = []

        for report in reports:

            user_name = ""

            if report.user_id:

                user = User.query.get(
                    report.user_id
                )

                if user:
                    user_name = user.name

            result.append({

                "id":
                    report.id,

                "user_id":
                    report.user_id,

                "user_name":
                    user_name,

                "post_id":
                    report.post_id,

                "report_type":
                    report.report_type,

                "reason":
                    report.reason,

                "status":
                    report.status

            })

        return jsonify({

            "success": True,
            "reports": result

        }), 200

    except Exception as e:

        print(
            "ADMIN REPORTS ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to load reports"

        }), 500


# =========================================================
# ADMIN REPORT STATUS
# =========================================================

@app.route(
    "/api/admin/reports/<int:report_id>",
    methods=["PUT"]
)
@jwt_required()
def admin_update_report(report_id):

    try:

        admin, error = admin_required()

        if error:
            return error

        report = Report.query.get(
            report_id
        )

        if not report:

            return jsonify({

                "success": False,
                "message":
                    "Report not found"

            }), 404

        data = request.get_json() or {}

        new_status = (
            data.get("status") or ""
        ).strip().lower()

        allowed_statuses = [
            "pending",
            "reviewed",
            "resolved",
            "rejected"
        ]

        if new_status not in allowed_statuses:

            return jsonify({

                "success": False,
                "message":
                    "Invalid report status"

            }), 400

        report.status = new_status

        db.session.commit()

        return jsonify({

            "success": True,

            "message":
                "Report status updated successfully"

        }), 200

    except Exception as e:

        db.session.rollback()

        print(
            "ADMIN REPORT UPDATE ERROR:",
            str(e)
        )

        return jsonify({

            "success": False,
            "message":
                "Unable to update report"

        }), 500

# =========================
# DATABASE TEST
# =========================

@app.route("/db-test")
def db_test():
    try:
        db.session.execute(
            db.text("SELECT 1")
        )

        return "Database connected successfully"

    except Exception as e:

        return f"Database connection failed: {e}"
           
# =========================
# RUN FLASK SERVER
# =========================
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)