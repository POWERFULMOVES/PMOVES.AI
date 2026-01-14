#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER="${WGER_CONTAINER_NAME:-pmoves-wger}"
WAIT_SECS="${WGER_BRAND_WAIT_SECS:-120}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker command not found; skipping Wger brand defaults." >&2
  exit 0
fi

if ! docker ps --format '{{.Names}}' | grep -qx "${CONTAINER}"; then
  echo "Wger container ${CONTAINER} is not running; skipping brand defaults." >&2
  exit 0
fi

SITE_URL="${WGER_SITE_URL:-http://localhost:8000}"
BRAND_SITE_NAME="${WGER_BRAND_SITE_NAME:-PMOVES Health Portal}"
BRAND_GYM_NAME="${WGER_BRAND_GYM_NAME:-PMOVES Health Lab}"
BRAND_GYM_CITY="${WGER_BRAND_GYM_CITY:-Distributed Mesh}"
BRAND_ADMIN_FIRST="${WGER_BRAND_ADMIN_FIRST_NAME:-PMOVES}"
BRAND_ADMIN_LAST="${WGER_BRAND_ADMIN_LAST_NAME:-Ops}"
BRAND_ADMIN_EMAIL="${WGER_BRAND_ADMIN_EMAIL:-ops@cataclysmstudios.com}"
BRAND_ADMIN_USERNAME="${WGER_BRAND_ADMIN_USERNAME:-admin}"

deadline=$((SECONDS + WAIT_SECS))
until docker exec "${CONTAINER}" bash -lc "cd /home/wger/src && python3 manage.py check >/dev/null 2>&1"; do
  if (( SECONDS >= deadline )); then
    echo "Wger container did not become ready within ${WAIT_SECS}s; skipping brand defaults." >&2
    exit 1
  fi
  sleep 3
done

until docker exec "${CONTAINER}" bash -lc 'cd /home/wger/src && python3 - <<'"'PY'"'
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")

try:
    import django
    django.setup()
    from django.contrib.sites.models import Site
    Site.objects.get_current()
except Exception:
    sys.exit(1)
sys.exit(0)
PY'; do
  if (( SECONDS >= deadline )); then
    echo "Wger database (django_site) not ready within ${WAIT_SECS}s; skipping brand defaults." >&2
    exit 1
  fi
  sleep 3
done

docker exec \
  -e BRAND_SITE_NAME="${BRAND_SITE_NAME}" \
  -e BRAND_SITE_URL="${SITE_URL}" \
  -e BRAND_GYM_NAME="${BRAND_GYM_NAME}" \
  -e BRAND_GYM_CITY="${BRAND_GYM_CITY}" \
  -e BRAND_ADMIN_FIRST_NAME="${BRAND_ADMIN_FIRST}" \
  -e BRAND_ADMIN_LAST_NAME="${BRAND_ADMIN_LAST}" \
  -e BRAND_ADMIN_EMAIL="${BRAND_ADMIN_EMAIL}" \
  -e BRAND_ADMIN_USERNAME="${BRAND_ADMIN_USERNAME}" \
  "${CONTAINER}" bash -lc 'cd /home/wger/src && python3 - <<'"'"'PY'"'"'
import os
import sys
from urllib.parse import urlparse

import django

sys.path.append(os.getcwd())
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "settings")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from wger.gym.models import Gym

site_name = os.environ["BRAND_SITE_NAME"]
site_url = os.environ.get("BRAND_SITE_URL", site_name)
parsed = urlparse(site_url)
domain = parsed.netloc or site_url

site = Site.objects.get_current()
site.name = site_name
site.domain = domain
site.save()

User = get_user_model()
username = os.environ.get("BRAND_ADMIN_USERNAME", "admin")
admin = User.objects.filter(username=username).first()
if admin:
    admin.first_name = os.environ.get("BRAND_ADMIN_FIRST_NAME", "") or admin.first_name
    admin.last_name = os.environ.get("BRAND_ADMIN_LAST_NAME", "") or admin.last_name
    email = os.environ.get("BRAND_ADMIN_EMAIL")
    if email:
        admin.email = email
    admin.is_staff = True
    admin.save()

gym = Gym.objects.order_by("id").first()
if gym:
    gym.name = os.environ.get("BRAND_GYM_NAME", gym.name)
    city = os.environ.get("BRAND_GYM_CITY")
    if city:
        gym.city = city
    gym.save()
PY'

echo "Applied Wger brand defaults to ${CONTAINER}."
