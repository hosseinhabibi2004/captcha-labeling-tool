"""
Authentication utilities for user management.
"""

import os
import json
from functools import wraps
from flask import session, jsonify, redirect, url_for, request
from file_lock import safe_write_json


def get_users_file_path():
    """
    Get the path to users.json file in the storage directory.
    Uses the same BASE_DIR logic as app.py
    """
    base_dir = os.environ.get(
        "RESULTS_BASE_DIR", os.path.join(os.path.dirname(__file__), "..", "storage")
    )
    base_dir = os.path.abspath(base_dir)
    users_file = os.path.join(base_dir, "users.json")
    # Ensure storage directory exists
    os.makedirs(base_dir, exist_ok=True)
    return users_file


# Path to users.json file
USERS_FILE = get_users_file_path()


def load_users():
    """
    Load users from users.json file.

    Returns:
        List of user dictionaries (empty list if file doesn't exist or is empty)
    """
    # Update USERS_FILE path in case BASE_DIR changed
    global USERS_FILE
    USERS_FILE = get_users_file_path()
    
    if not os.path.exists(USERS_FILE):
        return []

    try:
        # Check if file is empty
        if os.path.getsize(USERS_FILE) == 0:
            return []
        
        # Read users.json directly (it's a list, not a dict)
        # User changes are infrequent, so simple file read is fine
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users_data = json.load(f)
            # Handle both list and dict formats
            if isinstance(users_data, list):
                return users_data if len(users_data) > 0 else []
            elif isinstance(users_data, dict):
                # Convert dict to list
                return list(users_data.values()) if len(users_data) > 0 else []
            else:
                return []
    except json.JSONDecodeError:
        # File exists but is invalid JSON - treat as empty
        return []
    except Exception as e:
        # Log error for debugging
        import logging

        logging.error(f"Error loading users from {USERS_FILE}: {e}")
        return []


def save_users(users):
    """
    Save users to users.json file.

    Args:
        users: List of user dictionaries
    """
    # Update USERS_FILE path in case BASE_DIR changed
    global USERS_FILE
    USERS_FILE = get_users_file_path()
    safe_write_json(USERS_FILE, users)


def get_user(username):
    """
    Get user by username.

    Args:
        username: Username to look up

    Returns:
        User dict or None if not found
    """
    users = load_users()
    for user in users:
        if user.get("username") == username:
            return user
    return None


def validate_user(username, password):
    """
    Validate username and password.

    Args:
        username: Username
        password: Password (plain text)

    Returns:
        User dict if valid, None otherwise
    """
    user = get_user(username)
    if user and user.get("password") == password:
        return user
    return None


def login_required(f):
    """
    Decorator to require login for a route.
    For API routes, returns JSON error.
    For page routes, redirects to login.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("username"):
            # Check if this is an API route
            if request.path.startswith("/api/"):
                return jsonify(
                    {"success": False, "message": "Authentication required"}
                ), 401
            # For page routes, redirect to login
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorator to require admin login for a route.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("username"):
            if request.path.startswith("/api/"):
                return jsonify(
                    {"success": False, "message": "Authentication required"}
                ), 401
            return redirect(url_for("login_page"))
        if not session.get("is_admin"):
            if request.path.startswith("/api/"):
                return jsonify(
                    {"success": False, "message": "Admin access required"}
                ), 403
            return jsonify({"success": False, "message": "Admin access required"}), 403
        return f(*args, **kwargs)

    return decorated_function
