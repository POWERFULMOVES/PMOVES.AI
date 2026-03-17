#!/usr/bin/env python3
"""Fix SSL CA certificates in a container by copying certifi bundle to openssl path."""
import certifi
import shutil
import os
import ssl

src = certifi.where()
verify_paths = ssl.get_default_verify_paths()
dst_dir = os.path.dirname(verify_paths.openssl_cafile)
dst = os.path.join(dst_dir, "cacert.pem")

shutil.copy2(src, dst)
print(f"Updated: {dst} ({os.path.getsize(dst)} bytes)")

# Verify
import urllib.request
try:
    r = urllib.request.urlopen("https://huggingface.co", timeout=10)
    print(f"HuggingFace SSL: {r.status}")
except Exception as e:
    print(f"SSL still failing: {e}")
