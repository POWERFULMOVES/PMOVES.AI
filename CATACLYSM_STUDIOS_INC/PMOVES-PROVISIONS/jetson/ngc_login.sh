#!/usr/bin/env bash
echo "Login to NVIDIA NGC registry (nvcr.io). Username must be EXACTLY: $oauthtoken"
docker login nvcr.io -u '$oauthtoken'
