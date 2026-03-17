#!/usr/bin/env python3
"""Test HuggingFace SSL with explicit certifi CA bundle."""
import certifi
import ssl
import urllib.request

context = ssl.create_default_context(cafile=certifi.where())
r = urllib.request.urlopen("https://huggingface.co", timeout=10, context=context)
print(f"HF status: {r.status}")
print("SSL with explicit certifi: OK")
