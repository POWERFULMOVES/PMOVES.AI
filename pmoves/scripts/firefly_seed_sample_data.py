"""Seed Firefly III with the deterministic PMOVES 5-year projection dataset."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
from requests import exceptions as requests_exceptions

API_PREFIX = "/api/v1"
DEFAULT_TIMEOUT = 30


class FireflySeeder:
    """Helper for loading deterministic sample data into Firefly III."""

    def __init__(self, base_url: str, token: str, *, dry_run: bool = False, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "User-Agent": "pmoves-firefly-seeder/1.0",
            }
        )
        self.dry_run = dry_run
        self.timeout = timeout
        self._user_ids: Dict[str, str] = {}
        self._account_ids: Dict[str, str] = {}
        self._category_ids: Dict[str, str] = {}

    # ----------------------------- HTTP helpers -----------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        url = f"{self.base_url}{path}"
        try:
            resp = self.session.request(method, url, timeout=self.timeout, **kwargs)
        except requests_exceptions.RequestException as exc:
            raise RuntimeError(f"Firefly API {method} {path} failed: {exc}") from exc
        if resp.status_code >= 400:
            try:
                payload = resp.json()
            except ValueError:
                payload = resp.text
            raise RuntimeError(f"Firefly API {method} {path} failed: {resp.status_code} → {payload}")
        return resp

    def _maybe_request(self, method: str, path: str, **kwargs: Any) -> Optional[requests.Response]:
        if self.dry_run:
            print(f"[dry-run] {method} {path} {json.dumps(kwargs, default=str)}")
            return None
        return self._request(method, path, **kwargs)

    # ----------------------------- entity ensure ----------------------------

    def ensure_users(self, users: Iterable[Dict[str, Any]]) -> None:
        for user in users:
            email = user["email"].lower()
            if email in self._user_ids:
                continue
            user_id = self._lookup_user(email)
            if user_id:
                print(f"✔ User exists: {email} (id={user_id})")
                self._user_ids[email] = user_id
                continue
            user_id = self._create_user(user)
            if user_id:
                self._user_ids[email] = user_id

    def _lookup_user(self, email: str) -> Optional[str]:
        resp = self._request("GET", f"{API_PREFIX}/users", params={"search": email, "limit": 50})
        data = resp.json().get("data", [])
        for entry in data:
            attributes = entry.get("attributes", {})
            if attributes.get("email", "").lower() == email:
                return str(entry.get("id"))
        return None

    def _create_user(self, user: Dict[str, Any]) -> Optional[str]:
        payload = {
            key: value
            for key, value in user.items()
            if key in {"email", "name", "password", "role", "blocked", "language", "currency_code"}
        }
        print(f"→ Creating user {payload['email']}")
        resp = self._maybe_request("POST", f"{API_PREFIX}/users", json=payload)
        if resp is None:
            return None
        return str(resp.json().get("data", {}).get("id"))

    def ensure_categories(self, categories: Iterable[Dict[str, Any]], *, user_email: Optional[str] = None) -> None:
        owner_id = self._user_ids.get(user_email.lower()) if user_email else None
        for category in categories:
            name = category["name"]
            if name in self._category_ids:
                continue
            category_id = self._lookup_category(name)
            if category_id:
                print(f"✔ Category exists: {name} (id={category_id})")
                self._category_ids[name] = category_id
                continue
            category_id = self._create_category(category, owner_id=owner_id)
            if category_id:
                self._category_ids[name] = category_id

    def _lookup_category(self, name: str) -> Optional[str]:
        resp = self._request("GET", f"{API_PREFIX}/categories", params={"search": name, "limit": 50})
        data = resp.json().get("data", [])
        for entry in data:
            attributes = entry.get("attributes", {})
            if attributes.get("name") == name:
                return str(entry.get("id"))
        return None

    def _create_category(self, category: Dict[str, Any], *, owner_id: Optional[str]) -> Optional[str]:
        payload: Dict[str, Any] = {
            key: category[key]
            for key in ("name", "notes")
            if key in category
        }
        if category.get("tags"):
            payload["tag_names"] = category["tags"]
        if owner_id:
            payload["user_id"] = owner_id
        print(f"→ Creating category {payload['name']}")
        resp = self._maybe_request("POST", f"{API_PREFIX}/categories", json=payload)
        if resp is None:
            return None
        return str(resp.json().get("data", {}).get("id"))

    def ensure_accounts(self, accounts: Iterable[Dict[str, Any]]) -> None:
        for account in accounts:
            name = account["name"]
            if name in self._account_ids:
                continue
            account_id = self._lookup_account(name, account.get("type"))
            if account_id:
                print(f"✔ Account exists: {name} (id={account_id})")
                self._account_ids[name] = account_id
                continue
            account_id = self._create_account(account)
            if account_id:
                self._account_ids[name] = account_id

    def _lookup_account(self, name: str, account_type: Optional[str]) -> Optional[str]:
        params = {"search": name, "limit": 50}
        if account_type:
            params["type"] = account_type
        resp = self._request("GET", f"{API_PREFIX}/accounts", params=params)
        data = resp.json().get("data", [])
        for entry in data:
            attributes = entry.get("attributes", {})
            if attributes.get("name") == name and (
                account_type is None or attributes.get("type") == account_type
            ):
                return str(entry.get("id"))
        return None

    def _create_account(self, account: Dict[str, Any]) -> Optional[str]:
        payload: Dict[str, Any] = {
            key: account[key]
            for key in (
                "name",
                "type",
                "currency_code",
                "opening_balance",
                "opening_balance_date",
                "notes",
                "account_role",
            )
            if key in account
        }
        owner_email = account.get("owner_email")
        if owner_email:
            owner_id = self._user_ids.get(owner_email.lower())
            if owner_id:
                payload["user_id"] = owner_id
        print(f"→ Creating account {payload['name']} ({account.get('type')})")
        resp = self._maybe_request("POST", f"{API_PREFIX}/accounts", json=payload)
        if resp is None:
            return None
        return str(resp.json().get("data", {}).get("id"))

    # ----------------------------- transactions -----------------------------

    def seed_transactions(self, transactions: Iterable[Dict[str, Any]]) -> None:
        for tx in transactions:
            external_id = tx.get("external_id")
            if external_id and self._transaction_exists(external_id):
                print(f"✔ Transaction exists: {external_id}")
                continue
            self._create_transaction(tx)

    def _transaction_exists(self, external_id: str) -> bool:
        resp = self._request("GET", f"{API_PREFIX}/transactions", params={"search": external_id, "limit": 1})
        data = resp.json().get("data", [])
        for entry in data:
            attributes = entry.get("attributes", {})
            if attributes.get("external_id") == external_id:
                return True
        return False

    def _create_transaction(self, tx: Dict[str, Any]) -> None:
        tx_type = tx["type"]
        payload: Dict[str, Any] = {
            "apply_rules": True,
            "fire_webhooks": False,
            "transactions": [
                self._build_transaction_entry(tx_type, tx),
            ],
        }
        print(f"→ Posting transaction {tx.get('external_id', tx.get('description'))} [{tx_type}]")
        self._maybe_request("POST", f"{API_PREFIX}/transactions", json=payload)

    def _build_transaction_entry(self, tx_type: str, tx: Dict[str, Any]) -> Dict[str, Any]:
        entry: Dict[str, Any] = {
            "type": tx_type,
            "date": tx["date"],
            "amount": str(tx["amount"]),
            "description": tx.get("description"),
            "currency_code": tx.get("currency_code", "USD"),
            "notes": tx.get("notes"),
            "category_name": tx.get("category_name"),
            "external_id": tx.get("external_id"),
            "tags": tx.get("tags", []),
        }
        owner_id = self._user_ids.get(tx.get("owner_email", "").lower()) if tx.get("owner_email") else None
        if owner_id:
            entry["user_id"] = owner_id
        source_name = tx.get("source_name")
        dest_name = tx.get("destination_name")
        if tx_type == "deposit":
            entry["source_id"] = self._account_id_for(source_name)
            entry["destination_id"] = self._account_id_for(dest_name)
        elif tx_type == "withdrawal":
            entry["source_id"] = self._account_id_for(source_name)
            entry["destination_id"] = self._account_id_for(dest_name)
        elif tx_type == "transfer":
            entry["source_id"] = self._account_id_for(source_name)
            entry["destination_id"] = self._account_id_for(dest_name)
        else:
            raise ValueError(f"Unsupported transaction type: {tx_type}")
        return entry

    def _account_id_for(self, name: Optional[str]) -> str:
        if not name:
            raise ValueError("Transaction entry missing account reference")
        account_id = self._account_ids.get(name)
        if not account_id:
            raise KeyError(f"Account '{name}' not known; ensure accounts are seeded first")
        return account_id


def load_fixture(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_fixture(path_arg: Optional[str]) -> Path:
    if path_arg:
        return Path(path_arg).expanduser().resolve()
    root = Path(__file__).resolve().parent.parent
    return root / "data" / "firefly" / "sample_transactions.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", dest="base_url", default=os.getenv("FIREFLY_BASE_URL"), help="Firefly III base URL")
    parser.add_argument(
        "--token",
        dest="token",
        default=os.getenv("FIREFLY_ACCESS_TOKEN"),
        help="Firefly III personal access token",
    )
    parser.add_argument("--fixture", dest="fixture", default=None, help="Path to JSON fixture to load")
    parser.add_argument("--dry-run", action="store_true", help="Print operations without executing them")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds (default: 30)")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.base_url:
        raise SystemExit("FIREFLY_BASE_URL is required (pass via --base-url or environment)")
    if not args.token:
        raise SystemExit("FIREFLY_ACCESS_TOKEN is required (pass via --token or environment)")

    fixture_path = resolve_fixture(args.fixture)
    if not fixture_path.exists():
        raise SystemExit(f"Fixture not found: {fixture_path}")

    payload = load_fixture(fixture_path)
    print(f"Loaded fixture {fixture_path} (version={payload.get('metadata', {}).get('version')})")

    seeder = FireflySeeder(args.base_url, args.token, dry_run=args.dry_run, timeout=args.timeout)
    users: List[Dict[str, Any]] = payload.get("users", [])
    if users:
        seeder.ensure_users(users)
    categories: List[Dict[str, Any]] = payload.get("categories", [])
    if categories:
        seeder.ensure_categories(categories, user_email=users[0]["email"] if users else None)
    accounts: List[Dict[str, Any]] = payload.get("accounts", [])
    if accounts:
        seeder.ensure_accounts(accounts)
    transactions: List[Dict[str, Any]] = payload.get("transactions", [])
    if transactions:
        seeder.seed_transactions(transactions)
    print("✔ Firefly sample dataset applied.")


if __name__ == "__main__":
    main()
