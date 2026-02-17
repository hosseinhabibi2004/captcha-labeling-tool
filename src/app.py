import os
import json
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    send_from_directory,
    redirect,
    url_for,
)
from file_lock import safe_read_json, safe_merge_json, safe_write_json
from bucket_manager import BucketManager
from sites import get_sites, get_site_paths
from auth import (
    login_required,
    admin_required,
    validate_user,
    load_users,
    save_users,
    get_user,
)

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for sessions

# Base directory for storage (configurable via environment variable)
BASE_DIR = os.environ.get(
    "RESULTS_BASE_DIR", os.path.join(os.path.dirname(__file__), "..", "storage")
)
BASE_DIR = os.path.abspath(BASE_DIR)

# Initialize bucket manager
BUCKET_SIZE = int(os.environ.get("BUCKET_SIZE", 20))
bucket_manager = BucketManager(BASE_DIR, BUCKET_SIZE)


# Helper functions to handle both flat and nested label structures
def get_label_value(label_data):
    """
    Extract label value from either flat string or nested object structure.

    Args:
        label_data: Either a string (old format) or dict (new format)

    Returns:
        String value or None
    """
    if label_data is None:
        return None
    if isinstance(label_data, str):
        return label_data
    if isinstance(label_data, dict):
        return label_data.get("value")
    return None


def is_labeled(label_data):
    """
    Check if image is labeled (handles both formats).

    Args:
        label_data: Either a string (old format) or dict (new format)

    Returns:
        True if labeled, False otherwise
    """
    if label_data is None:
        return False
    if isinstance(label_data, str):
        return True  # Any string value means labeled (including "__NULL__")
    if isinstance(label_data, dict):
        return "value" in label_data
    return False


def get_admin_review(label_data):
    """
    Get admin review data from label entry.

    Args:
        label_data: Either a string (old format) or dict (new format)

    Returns:
        Dict with admin_review data or None
    """
    if isinstance(label_data, dict):
        return label_data.get("admin_review")
    return None


def normalize_label_entry(filename, value, admin_review=None, labeled_by=None):
    """
    Create normalized label entry structure.

    Args:
        filename: Image filename
        value: Label value (string or "__NULL__")
        admin_review: Optional dict with admin review data
        labeled_by: Optional username who labeled this

    Returns:
        Dict with normalized structure
    """
    entry = {"value": value}
    if labeled_by:
        entry["labeled_by"] = labeled_by
    if admin_review:
        entry["admin_review"] = admin_review
    # If no admin_review and no labeled_by, return flat structure for backward compatibility
    if not admin_review and not labeled_by:
        return value
    return entry


# Authentication routes
@app.route("/setup", methods=["GET", "POST"])
def setup():
    """First-time setup page to create the first admin user."""
    users = load_users()
    
    # If users already exist, redirect to login
    if len(users) > 0:
        return redirect(url_for("login_page"))
    
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        password_confirm = data.get("password_confirm", "").strip()

        if not username or not password:
            error_msg = "Username and password required"
            if request.is_json:
                return jsonify({"success": False, "message": error_msg}), 400
            return render_template("setup.html", error=error_msg)
        
        if password != password_confirm:
            error_msg = "Passwords do not match"
            if request.is_json:
                return jsonify({"success": False, "message": error_msg}), 400
            return render_template("setup.html", error=error_msg)
        
        # Check if username already exists (shouldn't happen, but be safe)
        if get_user(username):
            error_msg = "Username already exists"
            if request.is_json:
                return jsonify({"success": False, "message": error_msg}), 400
            return render_template("setup.html", error=error_msg)
        
        # Create first user as admin
        new_user = {
            "username": username,
            "password": password,
            "is_admin": True  # First user is always admin
        }
        
        users = [new_user]
        save_users(users)
        
        # Auto-login the new admin user
        session["username"] = username
        session["is_admin"] = True
        
        if request.is_json:
            return jsonify({
                "success": True,
                "username": username,
                "is_admin": True,
                "message": "Admin user created successfully"
            })
        
        return redirect(url_for("index"))
    
    # GET request - show setup page
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Login page and handler."""
    # Check if setup is needed (no users exist)
    users = load_users()
    if len(users) == 0:
        return redirect(url_for("setup"))
    
    if request.method == "POST":
        data = request.get_json() if request.is_json else request.form
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            if request.is_json:
                return jsonify(
                    {"success": False, "message": "Username and password required"}
                ), 400
            return render_template("login.html", error="Username and password required")

        user = validate_user(username, password)
        if user:
            session["username"] = user["username"]
            session["is_admin"] = user.get("is_admin", False)
            if request.is_json:
                return jsonify(
                    {
                        "success": True,
                        "username": user["username"],
                        "is_admin": user.get("is_admin", False),
                    }
                )
            # Redirect based on whether user is admin or not
            next_url = request.args.get(
                "next", "/admin" if user.get("is_admin") else "/"
            )
            return redirect(next_url)
        else:
            error_msg = "Invalid username or password"
            if request.is_json:
                return jsonify({"success": False, "message": error_msg}), 401
            return render_template("login.html", error=error_msg)

    # GET request - show login page
    return render_template("login.html")


@app.route("/logout", methods=["POST", "GET"])
def logout():
    """Logout handler."""
    session.pop("username", None)
    session.pop("is_admin", None)
    if request.is_json or request.path.startswith("/api/"):
        return jsonify({"success": True, "message": "Logged out"})
    return redirect(url_for("login_page"))


@app.route("/api/me", methods=["GET"])
def get_current_user():
    """Get current user info from session."""
    username = session.get("username")
    is_admin = session.get("is_admin", False)
    if username:
        return jsonify({"success": True, "username": username, "is_admin": is_admin})
    return jsonify({"success": False, "message": "Not logged in"}), 401


@app.route("/api/sites", methods=["GET"])
@login_required
def get_sites_list():
    """Get list of available sites."""
    try:
        sites = get_sites(BASE_DIR)
        return jsonify({"success": True, "sites": sites})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/results/<site_id>/img/<path:filename>")
def serve_image(site_id, filename):
    """Serve image from site's img directory."""
    try:
        paths = get_site_paths(BASE_DIR, site_id)
        img_dir = paths["img"]
        return send_from_directory(img_dir, filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route("/")
@login_required
def index():
    """Main page - shows bucket assigned to current session."""
    # Get site from query parameter
    site_id = request.args.get("site")

    # If no site specified, redirect to first available site or show site selector
    if not site_id:
        sites = get_sites(BASE_DIR)
        if sites:
            username = session.get("username")
            is_admin = session.get("is_admin", False)
            return render_template(
                "index.html",
                files=[],
                labels={},
                bucket=None,
                session_id=None,
                sites=sites,
                current_site=None,
                username=username,
                is_admin=is_admin,
            )
        else:
            username = session.get("username")
            is_admin = session.get("is_admin", False)
            return render_template(
                "index.html",
                files=[],
                labels={},
                bucket=None,
                session_id=None,
                sites=[],
                current_site=None,
                username=username,
                is_admin=is_admin,
            )

    # Get or assign bucket for this session (prefer session_id from URL so post-redirect load works)
    session_id = request.args.get("session_id")
    if session_id and len(session_id) == 32:
        session["session_id"] = session_id
    else:
        session_id = session.get("session_id")
    if not session_id:
        session_id = os.urandom(16).hex()
        session["session_id"] = session_id

    # Get site paths
    paths = get_site_paths(BASE_DIR, site_id)
    labels_file = paths["labels"]

    # Ensure labels file exists
    if not os.path.exists(labels_file):
        os.makedirs(os.path.dirname(labels_file), exist_ok=True)
        with open(labels_file, "w") as fp:
            json.dump({}, fp)

    # Validate and clean up orphaned buckets before getting bucket
    bucket_manager.validate_and_cleanup_buckets(site_id, labels_file)

    bucket = bucket_manager.get_bucket_for_session(session_id, site_id, labels_file)

    if bucket is None:
        # All buckets completed or no images
        sites = get_sites(BASE_DIR)
        username = session.get("username")
        is_admin = session.get("is_admin", False)
        return render_template(
            "index.html",
            files=[],
            labels={},
            bucket=None,
            session_id=session_id,
            sites=sites,
            current_site=site_id,
            username=username,
            is_admin=is_admin,
        )

    # Get labels for bucket images
    labels = {}
    if os.path.exists(labels_file):
        try:
            all_labels = safe_read_json(labels_file)
            for img in bucket["images"]:
                label_data = all_labels.get(img)
                if label_data:
                    labels[img] = get_label_value(label_data) or ""
                else:
                    labels[img] = ""
        except:
            pass

    sites = get_sites(BASE_DIR)
    username = session.get("username")
    is_admin = session.get("is_admin", False)
    return render_template(
        "index.html",
        files=bucket["images"],
        labels=labels,
        bucket=bucket,
        session_id=session_id,
        sites=sites,
        current_site=site_id,
        username=username,
        is_admin=is_admin,
    )


@app.route("/api/bucket", methods=["GET"])
@login_required
def get_bucket():
    """API endpoint to get or assign a bucket for the current session."""
    # Require site parameter
    site_id = request.args.get("site")
    if not site_id:
        return jsonify({"success": False, "message": "Site parameter required"}), 400

    # Check if client sent session_id from localStorage
    client_session_id = request.args.get("session_id")

    session_id = session.get("session_id")
    if not session_id:
        # Try to use client-provided session_id if valid
        if client_session_id and len(client_session_id) == 32:  # hex string length
            session_id = client_session_id
            session["session_id"] = session_id
        else:
            session_id = os.urandom(16).hex()
            session["session_id"] = session_id

    # Get site paths
    paths = get_site_paths(BASE_DIR, site_id)
    labels_file = paths["labels"]

    # Ensure labels file exists
    if not os.path.exists(labels_file):
        os.makedirs(os.path.dirname(labels_file), exist_ok=True)
        with open(labels_file, "w") as fp:
            json.dump({}, fp)

    # Validate and clean up orphaned buckets before getting bucket
    bucket_manager.validate_and_cleanup_buckets(site_id, labels_file)

    bucket = bucket_manager.get_bucket_for_session(session_id, site_id, labels_file)

    if bucket is None:
        return jsonify(
            {"success": False, "message": "No buckets available or all completed"}
        ), 200

    # Get labels for bucket images
    labels = {}
    if os.path.exists(labels_file):
        try:
            all_labels = safe_read_json(labels_file)
            for img in bucket["images"]:
                label_data = all_labels.get(img)
                if label_data:
                    labels[img] = get_label_value(label_data) or ""
                else:
                    labels[img] = ""
        except:
            pass

    return jsonify(
        {
            "success": True,
            "site": site_id,
            "bucket": {
                "id": bucket["id"],
                "images": bucket["images"],
                "total_images": len(bucket["images"]),
            },
            "labels": labels,
            "session_id": session_id,
        }
    )


@app.route("/api/save", methods=["POST"])
@login_required
def save():
    """Save labels with file locking and bucket completion check."""
    # Require site parameter
    site_id = request.form.get("site")
    if not site_id:
        return jsonify({"success": False, "message": "Site parameter required"}), 400

    # Check if client sent session_id from localStorage
    client_session_id = request.form.get("session_id") or request.headers.get(
        "X-Session-ID"
    )

    session_id = session.get("session_id")
    if not session_id:
        # Try to use client-provided session_id if valid
        if client_session_id and len(client_session_id) == 32:  # hex string length
            session_id = client_session_id
            session["session_id"] = session_id
        else:
            return jsonify({"success": False, "message": "No session"}), 400

    # Get site paths
    paths = get_site_paths(BASE_DIR, site_id)
    labels_file = paths["labels"]

    # Ensure labels file exists
    if not os.path.exists(labels_file):
        os.makedirs(os.path.dirname(labels_file), exist_ok=True)
        with open(labels_file, "w") as fp:
            json.dump({}, fp)

    # Get labels from request (excluding special fields)
    labels = dict(request.form)
    labels.pop("site", None)
    labels.pop("session_id", None)

    # Handle null values - convert empty strings to null marker
    # Also convert to nested format with labeled_by
    processed_labels = {}
    NULL_MARKER = "__NULL__"
    username = session.get("username")

    # Read existing labels to preserve structure
    existing_labels = safe_read_json(labels_file)

    for key, value in labels.items():
        if value.strip() == "":
            label_value = NULL_MARKER
        else:
            label_value = value.strip()

        # Get existing label data to preserve admin_review if present
        existing_data = existing_labels.get(key)
        admin_review = None
        if isinstance(existing_data, dict):
            admin_review = existing_data.get("admin_review")

        # Create nested structure with labeled_by
        processed_labels[key] = normalize_label_entry(
            key, label_value, admin_review=admin_review, labeled_by=username
        )

    # Merge labels safely with file locking
    try:
        safe_merge_json(labels_file, processed_labels)

        # Check if current bucket is completed
        bucket = bucket_manager.get_bucket_for_session(session_id, site_id, labels_file)
        if bucket:
            # Check completion
            all_labels = safe_read_json(labels_file)
            bucket_completed = all(
                is_labeled(all_labels.get(img)) for img in bucket["images"]
            )

            return jsonify(
                {
                    "success": True,
                    "bucket_completed": bucket_completed,
                    "session_id": session_id,
                }
            )
        else:
            return jsonify({"success": True, "bucket_completed": False})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/progress", methods=["GET"])
@login_required
def get_progress():
    """Get labeling progress."""
    site_id = request.args.get("site")  # Optional - if None, returns global progress
    try:
        progress = bucket_manager.get_progress(site_id, None)
        return jsonify({"success": True, "progress": progress})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# Keep old /save endpoint for backward compatibility (deprecated)
@app.route("/save", methods=["POST"])
def save_old():
    """Legacy save endpoint - redirects to new API."""
    return save()


# Admin panel routes
@app.route("/admin")
@admin_required
def admin():
    """Admin review panel."""
    username = session.get("username")
    return render_template("admin.html", username=username)


@app.route("/api/admin/images", methods=["GET"])
@admin_required
def get_admin_images():
    """Get paginated list of labeled images for admin review."""
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 50))
        site_id = request.args.get("site")  # Optional filter by site
        hide_reviewed = request.args.get("hide_reviewed", "false").lower() == "true"

        labeled_images = []

        if site_id:
            # Single site
            paths = get_site_paths(BASE_DIR, site_id)
            labels_file = paths["labels"]

            if os.path.exists(labels_file):
                all_labels = safe_read_json(labels_file)
                for filename, label_data in all_labels.items():
                    value = get_label_value(label_data)
                    admin_review = get_admin_review(label_data)
                    labeled_by = None
                    if isinstance(label_data, dict):
                        labeled_by = label_data.get("labeled_by")
                    labeled_images.append(
                        {
                            "site": site_id,
                            "filename": filename,
                            "value": value or "",
                            "labeled_by": labeled_by,
                            "admin_review": admin_review,
                        }
                    )
        else:
            # All sites
            sites = get_sites(BASE_DIR)
            for site in sites:
                paths = get_site_paths(BASE_DIR, site)
                labels_file = paths["labels"]

                if os.path.exists(labels_file):
                    all_labels = safe_read_json(labels_file)
                    for filename, label_data in all_labels.items():
                        value = get_label_value(label_data)
                        admin_review = get_admin_review(label_data)
                        labeled_by = None
                        if isinstance(label_data, dict):
                            labeled_by = label_data.get("labeled_by")
                        labeled_images.append(
                            {
                                "site": site,
                                "filename": filename,
                                "value": value or "",
                                "labeled_by": labeled_by,
                                "admin_review": admin_review,
                            }
                        )

        # Filter out reviewed items if requested
        if hide_reviewed:
            labeled_images = [
                img for img in labeled_images
                if not img.get("admin_review") or not img["admin_review"].get("status")
            ]

        # Sort by site, then filename
        labeled_images.sort(key=lambda x: (x["site"], x["filename"]))

        # Paginate
        total = len(labeled_images)
        total_pages = (total + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_images = labeled_images[start_idx:end_idx]

        return jsonify(
            {
                "success": True,
                "images": paginated_images,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": total_pages,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/review", methods=["POST"])
@admin_required
def save_admin_review():
    """Save admin review for images."""
    try:
        data = request.get_json()
        if not data or "reviews" not in data:
            return jsonify({"success": False, "message": "Invalid request data"}), 400

        # Group reviews by site
        reviews_by_site = {}
        for review in data["reviews"]:
            site_id = review.get("site")
            if not site_id:
                return jsonify(
                    {"success": False, "message": "Site required for each review"}
                ), 400

            if site_id not in reviews_by_site:
                reviews_by_site[site_id] = []
            reviews_by_site[site_id].append(review)

        # Process each site's reviews
        for site_id, reviews in reviews_by_site.items():
            paths = get_site_paths(BASE_DIR, site_id)
            labels_file = paths["labels"]

            # Ensure labels file exists
            if not os.path.exists(labels_file):
                os.makedirs(os.path.dirname(labels_file), exist_ok=True)
                with open(labels_file, "w") as fp:
                    json.dump({}, fp)

            # Read existing labels
            all_labels = safe_read_json(labels_file)

            # Process each review
            for review in reviews:
                filename = review.get("filename")
                value = review.get("value")
                status = review.get("status")  # 'sure' or 'not_sure'

                if not filename:
                    continue

                # Get current label data
                current_data = all_labels.get(filename)

                # Determine new value (use provided value or keep existing)
                old_value = get_label_value(current_data) if current_data else None
                if value is not None:
                    new_value = value.strip() if value.strip() else "__NULL__"
                else:
                    # Keep existing value
                    new_value = old_value if old_value else "__NULL__"

                # Get reviewer username
                reviewer_username = session.get("username")

                # Check if admin changed the value
                value_changed = (value is not None and new_value != old_value)
                
                # If admin changed the value, update labeled_by to admin name
                if value_changed:
                    labeled_by = reviewer_username
                else:
                    # Get labeled_by from existing data if present
                    if isinstance(current_data, dict):
                        labeled_by = current_data.get("labeled_by")
                    elif current_data:
                        # If it's flat, we don't know who labeled it
                        labeled_by = None
                    else:
                        labeled_by = None

                # Create admin review structure with reviewed_by
                admin_review = None
                if status:
                    admin_review = {"status": status, "reviewed_by": reviewer_username}

                # Update label entry - always use nested structure if admin_review exists
                if admin_review:
                    # Use nested structure with admin_review
                    entry = {"value": new_value, "admin_review": admin_review}
                    if labeled_by:
                        entry["labeled_by"] = labeled_by
                    all_labels[filename] = entry
                else:
                    # If no admin review but value changed, preserve structure
                    if isinstance(current_data, dict):
                        # Preserve existing structure
                        entry = {"value": new_value}
                        if labeled_by:
                            entry["labeled_by"] = labeled_by
                        if current_data.get("admin_review"):
                            entry["admin_review"] = current_data.get("admin_review")
                        all_labels[filename] = entry
                    else:
                        # Convert flat to nested if we have labeled_by info
                        # Otherwise keep flat for backward compatibility
                        if labeled_by:
                            all_labels[filename] = {
                                "value": new_value,
                                "labeled_by": labeled_by,
                            }
                        else:
                            all_labels[filename] = new_value

            # Write back
            safe_write_json(labels_file, all_labels)

        return jsonify({"success": True, "message": "Review saved successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# User management APIs
@app.route("/api/admin/users", methods=["GET"])
@admin_required
def get_users():
    """Get list of all users."""
    try:
        users = load_users()
        # Don't send passwords in response
        safe_users = [
            {"username": u["username"], "is_admin": u.get("is_admin", False)}
            for u in users
        ]
        return jsonify({"success": True, "users": safe_users})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/users", methods=["POST"])
@admin_required
def create_or_update_user():
    """Create or update a user."""
    try:
        data = request.get_json()
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        is_admin = data.get("is_admin", False)

        if not username:
            return jsonify({"success": False, "message": "Username required"}), 400

        users = load_users()

        # Check if user exists
        user_index = None
        for i, u in enumerate(users):
            if u.get("username") == username:
                user_index = i
                break

        # Update or create user
        user_data = {"username": username, "is_admin": bool(is_admin)}
        if password:
            user_data["password"] = password
        elif user_index is not None:
            # Keep existing password if not provided
            user_data["password"] = users[user_index].get("password", "")

        if user_index is not None:
            users[user_index] = user_data
        else:
            if not password:
                return jsonify(
                    {"success": False, "message": "Password required for new user"}
                ), 400
            users.append(user_data)

        save_users(users)
        return jsonify({"success": True, "message": "User saved successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/users/<username>", methods=["DELETE"])
@admin_required
def delete_user(username):
    """Delete a user."""
    try:
        users = load_users()
        # Don't allow deleting yourself
        if username == session.get("username"):
            return jsonify(
                {"success": False, "message": "Cannot delete your own account"}
            ), 400

        # Filter out the user
        original_count = len(users)
        users = [u for u in users if u.get("username") != username]

        if len(users) == original_count:
            return jsonify({"success": False, "message": "User not found"}), 404

        save_users(users)
        return jsonify({"success": True, "message": "User deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
