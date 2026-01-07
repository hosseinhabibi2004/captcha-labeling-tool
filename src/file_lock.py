"""
File locking utilities for safe concurrent file operations.
Uses lock files for cross-platform compatibility.
"""
import os
import json
import time
import platform
import threading


class FileLock:
    """Context manager for file locking using lock files."""
    
    def __init__(self, filepath, timeout=10, retry_interval=0.1):
        """
        Initialize file lock.
        
        Args:
            filepath: Path to the file to lock
            timeout: Maximum time to wait for lock (seconds)
            retry_interval: Time between lock attempts (seconds)
        """
        self.filepath = filepath
        self.lock_filepath = filepath + '.lock'
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.lock_file_handle = None
        self._local_lock = threading.Lock()  # Thread-local lock
    
    def __enter__(self):
        """Acquire file lock."""
        start_time = time.time()
        
        # Ensure target file exists
        if not os.path.exists(self.filepath):
            with open(self.filepath, 'w') as f:
                json.dump({}, f)
        
        # Try to acquire lock
        while True:
            try:
                # Try to create lock file exclusively
                # On Windows, opening in 'x' mode will fail if file exists
                # On Unix, we can use os.open with O_CREAT | O_EXCL
                if platform.system() == 'Windows':
                    try:
                        self.lock_file_handle = open(self.lock_filepath, 'x')
                        self.lock_file_handle.write(str(os.getpid()))
                        self.lock_file_handle.flush()
                        # Lock acquired
                        return self
                    except FileExistsError:
                        # Lock file exists, wait and retry
                        pass
                else:
                    # Unix: use O_CREAT | O_EXCL for atomic file creation
                    try:
                        fd = os.open(self.lock_filepath, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                        self.lock_file_handle = os.fdopen(fd, 'w')
                        self.lock_file_handle.write(str(os.getpid()))
                        self.lock_file_handle.flush()
                        # Lock acquired
                        return self
                    except FileExistsError:
                        # Lock file exists, wait and retry
                        pass
                
                # Check timeout
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {self.filepath} within {self.timeout} seconds"
                    )
                
                # Wait before retrying
                time.sleep(self.retry_interval)
                
            except Exception as e:
                if isinstance(e, TimeoutError):
                    raise
                # Other errors - check timeout and retry
                if time.time() - start_time >= self.timeout:
                    raise TimeoutError(
                        f"Could not acquire lock on {self.filepath} within {self.timeout} seconds"
                    )
                time.sleep(self.retry_interval)
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Release file lock."""
        if self.lock_file_handle:
            try:
                self.lock_file_handle.close()
            except:
                pass
        
        # Remove lock file
        try:
            if os.path.exists(self.lock_filepath):
                os.remove(self.lock_filepath)
        except:
            pass


def safe_read_json(filepath):
    """
    Safely read JSON file with locking.
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        Dictionary containing JSON data
    """
    try:
        with FileLock(filepath, timeout=5):  # Reduced timeout for faster failure
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        # Ensure we return a dict, not None
                        return data if isinstance(data, dict) else {}
                except json.JSONDecodeError as e:
                    # Log JSON decode errors
                    import logging
                    logging.error(f"JSON decode error in {filepath}: {e}")
                    return {}
        return {}
    except Exception as e:
        # If lock acquisition fails, try reading directly as fallback
        import logging
        lock_filepath = filepath + '.lock'
        
        # Check if lock file is stale (older than 30 seconds)
        try:
            if os.path.exists(lock_filepath):
                lock_age = time.time() - os.path.getmtime(lock_filepath)
                if lock_age > 30:  # Lock file older than 30 seconds is considered stale
                    logging.warning(f"Stale lock file detected (age: {lock_age:.1f}s), removing it")
                    try:
                        os.remove(lock_filepath)
                    except:
                        pass
        except:
            pass
        
        # Always try direct read if lock fails (for read operations, it's safe)
        logging.warning(f"Lock acquisition failed for {filepath}, trying direct read: {e}")
        try:
            if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    result = data if isinstance(data, dict) else {}
                    logging.info(f"Direct read successful for {filepath}, got {len(result)} entries")
                    return result
        except Exception as direct_e:
            logging.error(f"Direct read also failed for {filepath}: {direct_e}", exc_info=True)
        return {}


def safe_write_json(filepath, data):
    """
    Safely write JSON file with locking.
    
    Args:
        filepath: Path to JSON file
        data: Dictionary to write
    """
    with FileLock(filepath):
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)


def safe_merge_json(filepath, new_data):
    """
    Safely merge new data into existing JSON file with locking.
    Preserves existing data and only updates/adds new entries.
    
    Args:
        filepath: Path to JSON file
        new_data: Dictionary with new/updated entries
        
    Returns:
        Updated dictionary
    """
    with FileLock(filepath):
        # Read existing data
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            try:
                with open(filepath, 'r') as f:
                    existing_data = json.load(f)
            except (json.JSONDecodeError, ValueError):
                existing_data = {}
        else:
            existing_data = {}
        
        # Merge new data
        existing_data.update(new_data)
        
        # Write back
        with open(filepath, 'w') as f:
            json.dump(existing_data, f, indent=2)
        
        return existing_data
