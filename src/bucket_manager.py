"""
Bucket management system for distributing images across multiple users.
"""
import os
import json
import threading
from file_lock import safe_read_json, safe_write_json


def is_labeled(label_data):
    """
    Check if image is labeled (handles both flat and nested formats).
    
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


class BucketManager:
    """Manages image buckets and assignments to users."""
    
    def __init__(self, images_dir, buckets_file, bucket_size=20):
        """
        Initialize bucket manager.
        
        Args:
            images_dir: Directory containing images
            buckets_file: Path to buckets.json file
            bucket_size: Number of images per bucket
        """
        self.images_dir = images_dir
        self.buckets_file = buckets_file
        self.bucket_size = bucket_size
        self.lock = threading.Lock()
        self._initialize_buckets()
    
    def _get_all_images(self):
        """Get list of all image files."""
        files = []
        if os.path.exists(self.images_dir):
            for f in os.listdir(self.images_dir):
                if os.path.isfile(os.path.join(self.images_dir, f)):
                    ext = os.path.splitext(f)[-1].lower()
                    if ext in [".jpg", ".jpeg", ".png"]:
                        files.append(f)
        return sorted(files)
    
    def _initialize_buckets(self):
        """Initialize or load bucket structure."""
        with self.lock:
            if os.path.exists(self.buckets_file):
                try:
                    data = safe_read_json(self.buckets_file)
                    # Validate structure
                    if 'buckets' in data and 'bucket_size' in data:
                        # Update bucket_size if changed
                        if data['bucket_size'] != self.bucket_size:
                            self._recreate_buckets()
                        return
                except (json.JSONDecodeError, KeyError):
                    pass
            
            # Create new bucket structure
            self._recreate_buckets()
    
    def _recreate_buckets(self):
        """Recreate bucket structure from images."""
        images = self._get_all_images()
        buckets = []
        
        for i in range(0, len(images), self.bucket_size):
            bucket_images = images[i:i + self.bucket_size]
            buckets.append({
                'id': len(buckets),
                'images': bucket_images,
                'assigned_to': None,
                'status': 'unassigned'  # unassigned, assigned, completed
            })
        
        data = {
            'buckets': buckets,
            'bucket_size': self.bucket_size
        }
        
        safe_write_json(self.buckets_file, data)
    
    def validate_and_cleanup_buckets(self, labels_file):
        """
        Validate buckets and release orphaned ones (assigned but incomplete).
        This helps when sessions are lost but buckets are still assigned.
        
        Args:
            labels_file: Path to labels.json to check completion
        """
        with self.lock:
            data = safe_read_json(self.buckets_file)
            buckets = data['buckets']
            changed = False
            
            for bucket in buckets:
                if bucket['status'] == 'assigned':
                    # Check if bucket is actually completed
                    if self._is_bucket_completed(bucket, labels_file):
                        bucket['status'] = 'completed'
                        bucket['assigned_to'] = None
                        changed = True
                    # Note: We don't release incomplete buckets here automatically
                    # as they might be actively worked on. They'll be reassigned
                    # in get_bucket_for_session if needed.
            
            if changed:
                safe_write_json(self.buckets_file, data)
    
    def get_bucket_for_session(self, session_id, labels_file):
        """
        Get or assign a bucket for a session.
        
        Args:
            session_id: Unique session identifier
            labels_file: Path to labels.json to check completion
            
        Returns:
            Dictionary with bucket info or None if no buckets available
        """
        with self.lock:
            data = safe_read_json(self.buckets_file)
            buckets = data['buckets']
            
            # Check if session already has an assigned bucket
            for bucket in buckets:
                if bucket['assigned_to'] == session_id and bucket['status'] == 'assigned':
                    # Check if bucket is completed
                    if self._is_bucket_completed(bucket, labels_file):
                        bucket['status'] = 'completed'
                        bucket['assigned_to'] = None
                        safe_write_json(self.buckets_file, data)
                    else:
                        return bucket
            
            # Find next unassigned bucket
            for bucket in buckets:
                if bucket['status'] == 'unassigned':
                    bucket['assigned_to'] = session_id
                    bucket['status'] = 'assigned'
                    safe_write_json(self.buckets_file, data)
                    return bucket
            
            # Check for incomplete assigned buckets (in case user disconnected)
            # Find buckets that are assigned but not completed
            for bucket in buckets:
                if bucket['status'] == 'assigned':
                    if not self._is_bucket_completed(bucket, labels_file):
                        # Reassign to new session (orphaned bucket)
                        bucket['assigned_to'] = session_id
                        safe_write_json(self.buckets_file, data)
                        return bucket
            
            # All buckets completed
            return None
    
    def _is_bucket_completed(self, bucket, labels_file):
        """
        Check if all images in bucket are labeled.
        
        Args:
            bucket: Bucket dictionary
            labels_file: Path to labels.json
            
        Returns:
            True if all images are labeled
        """
        if not os.path.exists(labels_file):
            return False
        
        try:
            labels = safe_read_json(labels_file)
            for image in bucket['images']:
                # Image is considered labeled if it has a value (including null marker)
                label_data = labels.get(image)
                if not is_labeled(label_data):
                    return False
            return True
        except:
            return False
    
    def release_bucket(self, session_id, labels_file):
        """
        Release bucket assigned to a session (for cleanup).
        
        Args:
            session_id: Session identifier
            labels_file: Path to labels.json to check completion
        """
        with self.lock:
            data = safe_read_json(self.buckets_file)
            buckets = data['buckets']
            
            for bucket in buckets:
                if bucket['assigned_to'] == session_id and bucket['status'] == 'assigned':
                    # Only release if not completed
                    if not self._is_bucket_completed(bucket, labels_file):
                        bucket['assigned_to'] = None
                        bucket['status'] = 'unassigned'
                        safe_write_json(self.buckets_file, data)
                    break
    
    def get_progress(self, labels_file):
        """
        Get overall labeling progress.
        
        Args:
            labels_file: Path to labels.json
            
        Returns:
            Dictionary with progress stats
        """
        with self.lock:
            data = safe_read_json(self.buckets_file)
            buckets = data['buckets']
            
            total_images = sum(len(b['images']) for b in buckets)
            labeled_images = 0
            
            if os.path.exists(labels_file):
                try:
                    labels = safe_read_json(labels_file)
                    # Count all images that have labels (including null markers)
                    labeled_images = len(labels)
                except:
                    pass
            
            completed_buckets = sum(1 for b in buckets if b['status'] == 'completed')
            assigned_buckets = sum(1 for b in buckets if b['status'] == 'assigned')
            
            return {
                'total_images': total_images,
                'labeled_images': labeled_images,
                'total_buckets': len(buckets),
                'completed_buckets': completed_buckets,
                'assigned_buckets': assigned_buckets,
                'progress_percent': (labeled_images / total_images * 100) if total_images > 0 else 0
            }

