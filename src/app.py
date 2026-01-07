import os
import json
from flask import Flask, render_template, request, Response, jsonify, session
from file_lock import safe_read_json, safe_merge_json, safe_write_json
from bucket_manager import BucketManager

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for sessions

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
labels_file = os.path.join(STATIC_DIR, "labels.json")
buckets_file = os.path.join(STATIC_DIR, "buckets.json")
images_dir = os.path.join(STATIC_DIR, "img")

# Initialize bucket manager
BUCKET_SIZE = int(os.environ.get('BUCKET_SIZE', 20))
bucket_manager = BucketManager(images_dir, buckets_file, BUCKET_SIZE)

# Ensure labels file exists
if not os.path.exists(labels_file):
    with open(labels_file, "w") as fp:
        json.dump({}, fp)


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
        return label_data.get('value')
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
        return 'value' in label_data
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
        return label_data.get('admin_review')
    return None


def normalize_label_entry(filename, value, admin_review=None):
    """
    Create normalized label entry structure.
    
    Args:
        filename: Image filename
        value: Label value (string or "__NULL__")
        admin_review: Optional dict with admin review data
        
    Returns:
        Dict with normalized structure
    """
    if admin_review:
        return {
            'value': value,
            'admin_review': admin_review
        }
    return value  # Keep flat structure if no admin review


@app.route("/")
def index():
    """Main page - shows bucket assigned to current session."""
    # Get or assign bucket for this session
    session_id = session.get('session_id')
    if not session_id:
        session_id = os.urandom(16).hex()
        session['session_id'] = session_id
    
    # Validate and clean up orphaned buckets before getting bucket
    bucket_manager.validate_and_cleanup_buckets(labels_file)
    
    bucket = bucket_manager.get_bucket_for_session(session_id, labels_file)
    
    if bucket is None:
        # All buckets completed or no images
        return render_template("index.html", files=[], labels={}, bucket=None, session_id=session_id)
    
    # Get labels for bucket images
    labels = {}
    if os.path.exists(labels_file):
        try:
            all_labels = safe_read_json(labels_file)
            for img in bucket['images']:
                label_data = all_labels.get(img)
                if label_data:
                    labels[img] = get_label_value(label_data) or ""
                else:
                    labels[img] = ""
        except:
            pass
    
    return render_template("index.html", 
                          files=bucket['images'], 
                          labels=labels, 
                          bucket=bucket,
                          session_id=session_id)


@app.route("/api/bucket", methods=["GET"])
def get_bucket():
    """API endpoint to get or assign a bucket for the current session."""
    # Check if client sent session_id from localStorage
    client_session_id = request.args.get('session_id')
    
    session_id = session.get('session_id')
    if not session_id:
        # Try to use client-provided session_id if valid
        if client_session_id and len(client_session_id) == 32:  # hex string length
            session_id = client_session_id
            session['session_id'] = session_id
        else:
            session_id = os.urandom(16).hex()
            session['session_id'] = session_id
    
    # Validate and clean up orphaned buckets before getting bucket
    bucket_manager.validate_and_cleanup_buckets(labels_file)
    
    bucket = bucket_manager.get_bucket_for_session(session_id, labels_file)
    
    if bucket is None:
        return jsonify({
            'success': False,
            'message': 'No buckets available or all completed'
        }), 200
    
    # Get labels for bucket images
    labels = {}
    if os.path.exists(labels_file):
        try:
            all_labels = safe_read_json(labels_file)
            for img in bucket['images']:
                label_data = all_labels.get(img)
                if label_data:
                    labels[img] = get_label_value(label_data) or ""
                else:
                    labels[img] = ""
        except:
            pass
    
    return jsonify({
        'success': True,
        'bucket': {
            'id': bucket['id'],
            'images': bucket['images'],
            'total_images': len(bucket['images'])
        },
        'labels': labels,
        'session_id': session_id
    })


@app.route("/api/save", methods=["POST"])
def save():
    """Save labels with file locking and bucket completion check."""
    # Check if client sent session_id from localStorage
    client_session_id = request.form.get('session_id') or request.headers.get('X-Session-ID')
    
    session_id = session.get('session_id')
    if not session_id:
        # Try to use client-provided session_id if valid
        if client_session_id and len(client_session_id) == 32:  # hex string length
            session_id = client_session_id
            session['session_id'] = session_id
        else:
            return jsonify({'success': False, 'message': 'No session'}), 400
    
    # Get labels from request
    labels = dict(request.form)
    
    # Handle null values - convert empty strings to null marker
    processed_labels = {}
    NULL_MARKER = "__NULL__"
    for key, value in labels.items():
        if value.strip() == "":
            processed_labels[key] = NULL_MARKER
        else:
            processed_labels[key] = value.strip()
    
    # Merge labels safely with file locking
    try:
        safe_merge_json(labels_file, processed_labels)
        
        # Check if current bucket is completed
        bucket = bucket_manager.get_bucket_for_session(session_id, labels_file)
        if bucket:
            # Check completion
            all_labels = safe_read_json(labels_file)
            bucket_completed = all(
                is_labeled(all_labels.get(img)) for img in bucket['images']
            )
            
            return jsonify({
                'success': True,
                'bucket_completed': bucket_completed,
                'session_id': session_id
            })
        else:
            return jsonify({
                'success': True,
                'bucket_completed': False
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route("/api/progress", methods=["GET"])
def get_progress():
    """Get overall labeling progress."""
    try:
        progress = bucket_manager.get_progress(labels_file)
        return jsonify({
            'success': True,
            'progress': progress
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


# Keep old /save endpoint for backward compatibility (deprecated)
@app.route("/save", methods=["POST"])
def save_old():
    """Legacy save endpoint - redirects to new API."""
    return save()


# Admin panel routes
@app.route("/admin")
def admin():
    """Admin review panel."""
    return render_template("admin.html")


@app.route("/api/admin/images", methods=["GET"])
def get_admin_images():
    """Get paginated list of labeled images for admin review."""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 50))
        
        if not os.path.exists(labels_file):
            return jsonify({
                'success': True,
                'images': [],
                'total': 0,
                'page': page,
                'per_page': per_page,
                'total_pages': 0
            })
        
        all_labels = safe_read_json(labels_file)
        
        # Convert to list of (filename, value, admin_review) tuples
        labeled_images = []
        for filename, label_data in all_labels.items():
            value = get_label_value(label_data)
            admin_review = get_admin_review(label_data)
            labeled_images.append({
                'filename': filename,
                'value': value or "",
                'admin_review': admin_review
            })
        
        # Sort by filename
        labeled_images.sort(key=lambda x: x['filename'])
        
        # Paginate
        total = len(labeled_images)
        total_pages = (total + per_page - 1) // per_page
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_images = labeled_images[start_idx:end_idx]
        
        return jsonify({
            'success': True,
            'images': paginated_images,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


@app.route("/api/admin/review", methods=["POST"])
def save_admin_review():
    """Save admin review for images."""
    try:
        data = request.get_json()
        if not data or 'reviews' not in data:
            return jsonify({
                'success': False,
                'message': 'Invalid request data'
            }), 400
        
        # Read existing labels
        all_labels = safe_read_json(labels_file)
        
        # Process each review
        for review in data['reviews']:
            filename = review.get('filename')
            value = review.get('value')
            status = review.get('status')  # 'sure' or 'not_sure'
            
            if not filename:
                continue
            
            # Get current label data
            current_data = all_labels.get(filename)
            
            # Determine new value (use provided value or keep existing)
            if value is not None:
                new_value = value.strip() if value.strip() else "__NULL__"
            else:
                # Keep existing value
                new_value = get_label_value(current_data) if current_data else "__NULL__"
            
            # Create admin review structure
            admin_review = None
            if status:
                admin_review = {
                    'status': status
                }
            
            # Update label entry
            if admin_review:
                # Use nested structure
                all_labels[filename] = {
                    'value': new_value,
                    'admin_review': admin_review
                }
            else:
                # If no admin review but value changed, keep flat structure
                # unless it was already nested
                if isinstance(current_data, dict) and 'admin_review' in current_data:
                    # Preserve existing admin review
                    all_labels[filename] = {
                        'value': new_value,
                        'admin_review': current_data.get('admin_review')
                    }
                else:
                    # Use flat structure
                    all_labels[filename] = new_value
        
        # Write back
        safe_write_json(labels_file, all_labels)
        
        return jsonify({
            'success': True,
            'message': 'Review saved successfully'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)
