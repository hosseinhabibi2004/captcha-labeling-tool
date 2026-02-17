"""
Site discovery and management for multi-site captcha labeling.
"""

import os


def get_sites(base_dir):
    """
    Discover sites from base directory.
    A site is a subdirectory that contains an 'img' folder.

    Args:
        base_dir: Base directory containing site folders

    Returns:
        List of site IDs (folder names)
    """
    sites = []
    if not os.path.exists(base_dir):
        return sites

    for item in os.listdir(base_dir):
        site_path = os.path.join(base_dir, item)
        if os.path.isdir(site_path):
            img_dir = os.path.join(site_path, "img")
            if os.path.exists(img_dir) and os.path.isdir(img_dir):
                sites.append(item)

    return sorted(sites)


def get_site_paths(base_dir, site_id):
    """
    Get paths for a specific site.

    Args:
        base_dir: Base directory containing site folders
        site_id: Site identifier (folder name)

    Returns:
        Dictionary with paths: {
            'base': site base path,
            'img': image directory path,
            'labels': labels.json path,
            'buckets': buckets.json path
        }
    """
    site_base = os.path.join(base_dir, site_id)
    return {
        "base": site_base,
        "img": os.path.join(site_base, "img"),
        "labels": os.path.join(site_base, "labels.json"),
        "buckets": os.path.join(site_base, "buckets.json"),
    }
