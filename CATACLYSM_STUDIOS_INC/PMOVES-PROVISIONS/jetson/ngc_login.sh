#!/usr/bin/env bash
#
# Helper script to log in to the NVIDIA NGC container registry.
#
# This script prompts the user for their NGC API key (which is used as the
# password) and uses the required username '$oauthtoken'.
#
echo "Login to NVIDIA NGC registry (nvcr.io). Username must be EXACTLY: $oauthtoken"
docker login nvcr.io -u '$oauthtoken'
