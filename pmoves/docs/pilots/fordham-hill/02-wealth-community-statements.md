<!-- PMOVES workflow fordham-pilot-convergence lane=wealth · needsHumanReview=True -->

# Fordham Hill Mesh Cooperative — Example Community Financial Statements

**Ledger system:** PMOVES-Wealth (Firefly III fork, strict double-entry, AGPL).
**Modeling:** the whole cooperative is ONE Firefly `UserGroup` ("financial administration"). Residents get read access; the treasurer writes.

> **DRAFT — REQUIRES ACCOUNTING / LEGAL REVIEW.** Every dollar below is **illustrative** and clearly labeled. Hosting cost, member due, and home counts are parameters, not adopted figures. Do not use in quorum/voting materials until an accountant and counsel review them.

---

## 1. Chart of accounts (maps 1:1 to Firefly enums)

Vocabulary verified in-repo this session:
- Account types — `PMOVES-Wealth/app/Enums/AccountTypeEnum.php:32,38,45` → `Asset account`, `Expense account`, `Revenue account`.
- Transaction types — `PMOVES-Wealth/app/Enums/TransactionTypeEnum.php:32,37,38` → `Deposit`, `Transfer`, `Withdrawal`.
- Member access roles — `PMOVES-Wealth/app/Enums/UserRoleEnum.php:34,37,61,70` → `ro` (READ_ONLY), `mng_trx` (MANAGE_TRANSACTIONS), `view_reports` (VIEW_REPORTS), `owner` (OWNER).

| Firefly account | `AccountTypeEnum` | Role in the co-op |
|---|---|---|
| Mesh Cooperative Treasury | `ASSET` (`account_role: defaultAsset`) | Holds the pooled fund; its `current_balance` **is** the running community surplus |
| Member Contributions | `REVENUE` | Source of every monthly member `Deposit` (tag per apartment) |
| KVM Hosting (Hostinger) | `EXPENSE` | Destination of monthly hosting `Withdrawal` |
| Uplink / Incidentals | `EXPENSE` | Domain/TLS, monitoring, misc `Withdrawal` |
| Next KVM Node / Gear (PiggyBank) | savings goal on the Treasury asset | Capital-reserve earmark via `Transfer` |

**Access (for public transparency at quorum):** residents = `GroupMembership` with `ro` + `view_reports`; treasurer = `mng_trx` (or `owner`). This is the exact "residents read, treasurer writes" primitive.

---

## 2. Illustrative assumptions (all parametric)

| Parameter | Illustrative value | Source / status |
|---|---|---|
| Separate premium each home pays today | **$35.00/mo** ($420/yr) | Given field datum |
| Pooled member due (flat monthly `Deposit`) | **$10.00/mo** ($120/yr) | Illustrative — not an adopted rate |
| KVM exit-node hosting | **$54.00/mo** = 3 nodes × $18/mo | Illustrative Hostinger KVM price; real invoice **not in repo** |
| Operating incidentals | **$16.00/mo** | Illustrative (domain, TLS, monitoring) |
| Home count *N* | **25** and **100** | Parametric, per task |
| KVM exit nodes | 3 (kvm2, kvm4-1, kvm4-2) | Given field datum |

Why a handful of nodes serves the whole building: measured household **peak** demand ~50 Mbps but busy-hour **average** is ~2–6 Mbps, so a few datacenter uplinks (kvm4-1 raw 845/347, kvm4-2 683/704 Mbps) cover the mesh — the same oversubscription logic ISPs use. This is why per-home cost collapses as homes join.

---

## 3. Monthly Income & Expense statement
*(Firefly report: `reports.report.default` — income vs expense vs net)*

### 3a. N = 25 homes

| Line | Firefly transaction | Flow | Amount |
|---|---|---|---:|
| Member contributions (25 × $10) | `Deposit` | Member Contributions (REVENUE) → Treasury (ASSET) | **+$250.00** |
| KVM exit-node hosting | `Withdrawal` | Treasury → KVM Hosting (EXPENSE) | −$54.00 |
| Uplink / incidentals | `Withdrawal` | Treasury → Uplink/Incidentals (EXPENSE) | −$16.00 |
| **Total operating expense** | | | **−$70.00** |
| **Net operating surplus** | | | **+$180.00** |
| *(memo) Capital-reserve earmark* | `Transfer` | Treasury → PiggyBank "Next KVM Node" | *$100.00* |

### 3b. N = 100 homes

| Line | Firefly transaction | Flow | Amount |
|---|---|---|---:|
| Member contributions (100 × $10) | `Deposit` | Member Contributions (REVENUE) → Treasury (ASSET) | **+$1,000.00** |
| KVM exit-node hosting | `Withdrawal` | Treasury → KVM Hosting (EXPENSE) | −$54.00 |
| Uplink / incidentals | `Withdrawal` | Treasury → Uplink/Incidentals (EXPENSE) | −$16.00 |
| **Total operating expense** | | | **−$70.00** |
| **Net operating surplus** | | | **+$930.00** |
| *(memo) Capital-reserve earmark* | `Transfer` | Treasury → PiggyBank "Next KVM Node" | *$400.00* |

> The `Transfer` line is asset→asset — it **earmarks** money for the next node/gear; it does not reduce total community equity. Firefly budgets/reserves apply only to withdrawals.

---

## 4. Pooled vs "buying premium alone" — the counterfactual

Firefly has **no** built-in pooled-vs-alone report (see gaps), so this table is computed outside Firefly and presented **alongside** the `default`/`audit` reports.

| Metric | Separate (each home alone) | Pooled (mesh co-op) | Per-home savings |
|---|---:|---:|---:|
| Monthly cost per home | $35.00 | $10.00 | **$25.00 (71.4%)** |
| Annual cost per home | $420.00 | $120.00 | **$300.00** |
| **Community total — 25 homes / mo** | $875.00 | $250.00 | **$625.00/mo** |
| **Community total — 25 homes / yr** | $10,500.00 | $3,000.00 | **$7,500.00/yr** |
| **Community total — 100 homes / mo** | $3,500.00 | $1,000.00 | **$2,500.00/mo** |
| **Community total — 100 homes / yr** | $42,000.00 | $12,000.00 | **$30,000.00/yr** |

**Cost-recovery floor** (if dues only covered exact operating cost of $70/mo): per-home share = $70 ÷ N → **$2.80 at 25 homes, $0.70 at 100 homes.** The true cost of the service is a fraction of $35; the $10 due mostly builds the community's own equity and reserve. Every home that joins lowers everyone's floor — the mesh strengthens with every node.

---

## 5. Annual summary (monthly × 12)

| Line | 25 homes | 100 homes |
|---|---:|---:|
| Member contributions (income) | $3,000.00 | $12,000.00 |
| KVM exit-node hosting | −$648.00 | −$648.00 |
| Uplink / incidentals | −$192.00 | −$192.00 |
| **Net community surplus** | **$2,160.00** | **$11,160.00** |
| Household savings vs buying alone | $7,500.00 | $30,000.00 |

---

## 6. Balance view — end of Year 1
*(Firefly: account `current_balance` + PiggyBank; report `reports.report.audit` for the itemized ledger the Committee on Elders reviews)*

### 25 homes

| Balance sheet (illustrative) | Amount |
|---|---:|
| **Assets** | |
| &nbsp;&nbsp;Mesh Cooperative Treasury (ASSET) | $2,160.00 |
| &nbsp;&nbsp;&nbsp;&nbsp;— earmarked: PiggyBank "Next KVM Node / Gear" | $1,200.00 |
| &nbsp;&nbsp;&nbsp;&nbsp;— unrestricted | $960.00 |
| **Liabilities** | $0.00 |
| **Community Fund (equity)** | **$2,160.00** |

### 100 homes

| Balance sheet (illustrative) | Amount |
|---|---:|
| **Assets** | |
| &nbsp;&nbsp;Mesh Cooperative Treasury (ASSET) | $11,160.00 |
| &nbsp;&nbsp;&nbsp;&nbsp;— earmarked: PiggyBank "Next KVM Node / Gear" | $4,800.00 |
| &nbsp;&nbsp;&nbsp;&nbsp;— unrestricted | $6,360.00 |
| **Liabilities** | $0.00 |
| **Community Fund (equity)** | **$11,160.00** |

Balances tie out: Assets − Liabilities = Community Fund = cumulative net surplus. Double-entry integrity is enforced by Firefly itself.

---

## 7. How to load these into PMOVES-Wealth

**Supported path today = the existing REST seeder** in the sibling submodule `PMOVES-ToKenism-Multi/integrations/firefly/` (per scout findings). Firefly's own account/transaction endpoints are the real interface:

1. **Create accounts** — `POST /api/v1/accounts` via `firefly-client.ts` `createAccount()`. One call per row in §1. Asset account needs `account_role: defaultAsset` + `opening_balance`; revenue/expense accounts take just `name` + `type`.
2. **Post transactions** — `POST /api/v1/transactions` via `firefly-client.ts` `createTransaction({ type, source, destination, category_name, budget_name })`:
   - member due → `type: "deposit"`, source = *Member Contributions*, destination = *Mesh Cooperative Treasury*
   - hosting → `type: "withdrawal"`, source = *Treasury*, destination = *KVM Hosting (Hostinger)*
   - reserve earmark → `type: "transfer"`, source = *Treasury*, destination = *PiggyBank*
3. **Auto-post monthly** — create a Firefly `Recurrence` (model `PMOVES-Wealth/app/Models/Recurrence.php`, per scout) for the recurring member deposit + hosting withdrawal, and a `Bill` for the monthly hosting subscription so it predicts/tracks paid-vs-unpaid.
4. **Generate the statements** — run `reports.report.default` (this §3/§5) and `reports.report.audit` (this §6 itemized) over the month/year; `GET /api/v1/summary/basic` and the Treasury `current_balance` give the live surplus.

**What must be written / fixed first (in-repo gaps, per scout — not blockers to the illustration, but blockers to real seeding):**
- No Fordham Hill coop-seed script or member roster exists. `export_sim_to_firefly.ts` seeds generic "Sim Agent" personal-finance data, **not** co-op treasury/expense accounts — a new coop-seed script must be written (can reuse `createAccount`/`createTransaction`).
- `createAccount()` does **not** set `user_group_id`, so seeded accounts land in the default admin, not the shared co-op UserGroup — extend it (or seed via the Firefly UI) so residents get read access.
- Env/token mismatch: `firefly-client.ts` defaults to `FIREFLY_URL=localhost:8080` + `FIREFLY_API_TOKEN`, but `PMOVES-Wealth/PMOVES.AI_INTEGRATION.md` specifies `FIREFLY_PORT=8075` (8080 collides with Agent Zero) + `FIREFLY_ACCESS_TOKEN`. Reconcile before seeding.
- **CSV import:** upstream Firefly III has a separate data-importer, but **no importer config exists in this repo** — do not assume a CSV drop-in path; the REST seeder above is the grounded route.

---

*Prepared for the Fordham Hill Committee on Elders pilot. All figures illustrative. DRAFT — REQUIRES ACCOUNTING/LEGAL REVIEW.*