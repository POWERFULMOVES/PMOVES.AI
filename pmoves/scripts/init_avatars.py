"""Initializes the 'avatars' bucket in Supabase Storage.

This script waits for the storage service to become available, then checks for
the existence of the 'avatars' bucket. If the bucket does not exist, it is
created and made public.
"""
import os, sys, json, time
import requests

STORAGE_URL = os.environ.get("SUPABASE_STORAGE_URL", os.environ.get("STORAGE_URL", "http://storage:5000"))
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

def req(method, path, **kwargs):
    """Sends an authenticated request to the Supabase Storage API.

    Args:
        method: The HTTP method (e.g., 'get', 'post').
        path: The API endpoint path.
        **kwargs: Additional arguments to pass to `requests.request`.

    Returns:
        The `requests.Response` object.
    """
    headers = kwargs.pop('headers', {})
    if SERVICE_KEY:
        headers['Authorization'] = f'Bearer {SERVICE_KEY}'
    headers.setdefault('content-type','application/json')
    url = f"{STORAGE_URL}{path}"
    return requests.request(method, url, headers=headers, timeout=20, **kwargs)

def main():
    """Main function to ensure the 'avatars' bucket exists."""
    # Wait for storage readiness
    for _ in range(20):
        try:
            r = req('get', '/status')
            if r.ok:
                break
        except Exception:
            pass
        time.sleep(1)
    # List buckets
    try:
        r = req('get', '/bucket')
        r.raise_for_status()
        names = {b.get('name') for b in (r.json() or [])}
    except Exception:
        names = set()
    if 'avatars' in names:
        print('Bucket avatars already exists')
        return
    # Create avatars bucket
    r = req('post', '/bucket', data=json.dumps({'name':'avatars','public': True}))
    if r.ok:
        print('Created bucket avatars (public=True)')
    else:
        print('Bucket create response:', r.status_code, r.text)

if __name__ == '__main__':
    main()

