# TALCO CETP Member Portal — Project Development Plan

**Client:** Talco–Dindigul Tanners Enviro Control Systems P Ltd (Dindigul CETP)
**Vendor:** Smartiva Technologies LLP
**Scope:** 40 member tanneries · 5 pump houses (A–E) · single tenant
**Budget:** ₹70,000 one-time
**Version:** 1.0 · Sep 2026

---

## 0. Ground rules (apply to every phase)

| # | Rule |
|---|---|
| G1 | Tally is the source of truth. The portal never computes a bill amount. |
| G2 | No AI / LLM / embedding search anywhere in the import or mapping path. |
| G3 | Fuzzy matching may only **rank suggestions for a human**. It may never select, post, or write an alias. |
| G4 | No stored `balance` column. Balance is always a query. |
| G5 | Staging rows are never deleted. They are the audit trail. |
| G6 | An import may never create or edit a tannery master row. |
| G7 | GSTIN, phone and email are never join keys. |
| G8 | Every phase ends with the manual UI test pack for that phase passing (see file 3). |

---

## 1. Technology stack

### Backend
| Layer | Choice | Version |
|---|---|---|
| Language | Python | 3.12 |
| Framework | FastAPI | 0.115+ |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | 1.13+ |
| Validation | Pydantic | v2 |
| Database | PostgreSQL | 16 |
| XML parsing | stdlib `re` + `html` | — |
| Excel reading | openpyxl | 3.1+ |
| PDF generation | WeasyPrint + Jinja2 | 62+ |
| Scheduling | APScheduler | 3.10+ |
| Testing | pytest | 8+ |
| Password hashing | passlib[bcrypt] | — |
| JWT | python-jose | — |

### Frontend
| Layer | Choice |
|---|---|
| Build | Vite + React 18 + TypeScript |
| Styling | TailwindCSS |
| Server state | TanStack Query |
| Tables | TanStack Table |
| Forms | React Hook Form + Zod |
| Router | React Router v6 |

### Infrastructure
- Docker Compose: `api`, `web`, `postgres`
- OVH VPS · Nginx reverse proxy · Let's Encrypt SSL
- SMTP: Zoho Mail or Brevo (never direct VPS SMTP)
- Backups: nightly `pg_dump` to a second location, 30-day retention

### Explicitly excluded
Celery · Redis · Kafka · Next.js · microservices · multi-tenant layer from the Bankers app · any LLM service.

### Docker note
WeasyPrint needs system libraries. Add to the API Dockerfile from day one:
```
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*
```

---

## 2. Repository layout

```
talco-portal/
├─ api/
│  ├─ app/
│  │  ├─ importer/            # Phase 1 — pure library, no DB, no web
│  │  │  ├─ parser.py         # Tally XML -> VoucherRow[]
│  │  │  ├─ normalize.py      # nkey(), split_party()
│  │  │  ├─ matcher.py        # resolve()
│  │  │  ├─ masters.py        # pump-house workbook -> Tannery[]
│  │  │  └─ tests/
│  │  │     ├─ fixtures/      # Treatment.xml Chrome.xml Sludge.xml Receipt.xml
│  │  │     │                 # A..E PUMP HOUSEMASTER DATA V6.xlsx
│  │  │     ├─ test_parser.py
│  │  │     ├─ test_normalize.py
│  │  │     └─ test_matcher.py
│  │  ├─ models/              # SQLAlchemy
│  │  ├─ schemas/             # Pydantic
│  │  ├─ routers/
│  │  ├─ services/
│  │  ├─ security/            # RBAC + scoped_query()
│  │  ├─ templates/           # Jinja2 invoice + email
│  │  └─ main.py
│  ├─ alembic/
│  └─ Dockerfile
├─ web/
│  ├─ src/{pages,components,api,hooks,types}
│  └─ Dockerfile
├─ docker-compose.yml
└─ docs/   # this plan, the tracker, the test guide, the import spec
```

---

## 3. Phase plan

Nine phases. Each is independently demonstrable. **Phase 1 carries the entire technical risk of the project and needs no database, no server and no UI** — do it first and prove it against the real August 2026 files.

---

### Phase 0 — Project setup
**Goal:** A repo that builds and runs an empty app on the dev machine and on the VPS.

| Task | Deliverable |
|---|---|
| P0-T01 | Git repo, branch strategy (`main` / `dev`), `.gitignore`, `.env.example` |
| P0-T02 | `docker-compose.yml` with api + web + postgres, healthchecks |
| P0-T03 | API Dockerfile including the WeasyPrint system libraries |
| P0-T04 | Vite + React + TS + Tailwind scaffold, `/health` page |
| P0-T05 | `GET /health` endpoint returning DB connectivity |
| P0-T06 | pytest configured, one passing dummy test |
| P0-T07 | Copy the 4 Aug XML files + 5 pump-house workbooks into `tests/fixtures/` |

**Exit criteria:** `docker compose up` gives a reachable API and web page. `pytest` runs green.
**Test pack:** TP-0

---

### Phase 1 — Importer core library ⚠️ highest risk
**Goal:** Given the real Tally files, produce fully resolved rows — with zero database involved.

| Task | Deliverable |
|---|---|
| P1-T01 | `masters.py` — read the five pump-house workbooks into 40 `Tannery` objects (sno, name, pump, ids, GPS, GST, consent, capacity, shares) |
| P1-T02 | `normalize.py` — `nkey()`: unescape → uppercase → `&`→`AND` → strip non-alphanumeric |
| P1-T03 | `normalize.py` — `split_party()`: strip `[-\s]*STEP\s*$`, split on `\bC\s*[/.]?\s*O\b[.,]?` |
| P1-T04 | `parser.py` — UTF-16 decode, `DBCFIXED` block split, extract date / party / GSTIN / gross / `DBCLEDAMT` series |
| P1-T05 | Tax assertion: `cgst == sgst` and `base × rate ≈ cgst + sgst` (±1). Failures collected, never silently dropped |
| P1-T06 | `matcher.py` — `resolve()` 4-step algorithm (alias → direct → C/o both-sides → queue) |
| P1-T07 | `suggest()` using `difflib.SequenceMatcher`, returns top 3, ordering only |
| P1-T08 | Unit tests against the August fixtures with the exact expected numbers in §4 below |

**Exit criteria:** all four August files resolve to 100% matched, and every control total in §4 reproduces exactly.
**Test pack:** TP-1 (automated; no UI yet)

---

### Phase 2 — Database and master load
**Goal:** The 40 tanneries live in PostgreSQL and can be browsed by the admin.

| Task | Deliverable |
|---|---|
| P2-T01 | Alembic migration: the 10 tables from the import spec |
| P2-T02 | Indexes: `invoice(tannery_id, invoice_date)`, `invoice(party_id, invoice_date)`, same pair on `receipt`, unique on `party.normalized_key`, `party_alias.normalized_key`, `invoice(voucher_no, fy)`, `import_batch.file_sha256` |
| P2-T03 | Seed `charge_head`: Treatment 5%, Chrome water 5%, Sludge disposal 18% |
| P2-T04 | Master import command: workbooks → `tannery` rows |
| P2-T05 | Data-quality report on load: blank GST, GST checksum failures, expired consent, invalid phone length, malformed email |
| P2-T06 | Admin master list + detail screens (read + edit) |

**Exit criteria:** 40 tanneries visible, filterable by pump house, editable by admin only.
**Test pack:** TP-2

---

### Phase 3 — Import pipeline
**Goal:** Admin uploads an XML and posts a batch.

| Task | Deliverable |
|---|---|
| P3-T01 | `POST /imports` — file + charge head + period + source type; SHA-256 duplicate guard |
| P3-T02 | Parse → staging rows, batch status `parsed` |
| P3-T03 | Run matcher, mark rows `matched` / `queued`, batch status `reviewed` |
| P3-T04 | Batch review screen: row count, matched/queued split, totals by charge head, tax check result, error list |
| P3-T05 | `POST /imports/{id}/post` — single transaction into `invoice` / `receipt` |
| P3-T06 | Upsert on `(voucher_no, fy)` with `invoice_revision` history |
| P3-T07 | Batch list screen with status, uploader, timestamps |
| P3-T08 | `partially_posted` state so a stuck name never blocks the batch |

**Exit criteria:** Admin imports all four August files unaided and the posted totals match §4.
**Test pack:** TP-3

---

### Phase 4 — Mapping queue
**Goal:** Every unmatched ledger name gets resolved by a human, once.

| Task | Deliverable |
|---|---|
| P4-T01 | Queue screen: raw name, split sides, ranked suggestions, batch context |
| P4-T02 | Action "Link to existing tannery" → creates party if new, writes `tannery_party_link` and `party_alias` |
| P4-T03 | `valid_from` date field on link, defaulted to batch period start |
| P4-T04 | Action "Not a member" → alias marked excluded, counted in batch summary |
| P4-T05 | Alias management screen (view, revoke) — admin only |
| P4-T06 | Owner ↔ lessee link approval, with role selection |

**Exit criteria:** A deliberately renamed ledger lands in the queue, is linked once, and auto-matches on the next import.
**Test pack:** TP-4

---

### Phase 5 — Auth, RBAC and portal
**Goal:** Members and lessees log in and see the correct — and only the correct — data.

| Task | Deliverable |
|---|---|
| P5-T01 | Auth reused from Bankers app, multi-tenant layer stripped |
| P5-T02 | Roles: `talco_admin`, `talco_staff`, `member`, `member_staff`, `lessee` |
| P5-T03 | Single `scoped_query()` helper in the repository layer — the only place row scope is applied |
| P5-T04 | User invite + first-login password set + password reset |
| P5-T05 | Member dashboard: outstanding, last bill, consent status, pump house |
| P5-T06 | Ledger screen with running balance (UNION invoice + receipt, window function) |
| P5-T07 | Invoice list + detail, receipt list |
| P5-T08 | Lessee view — party-scoped, tannery name shown for context only |

**Exit criteria:** A lessee login cannot see the owner's other ledgers by any URL, filter or API call.
**Test pack:** TP-5 — includes negative security tests

---

### Phase 6 — Invoice PDF and email
**Goal:** Bills reach members automatically after posting.

| Task | Deliverable |
|---|---|
| P6-T01 | Jinja2 invoice template — TALCO letterhead, GSTIN, SAC, CGST/SGST split, amount in words |
| P6-T02 | WeasyPrint render + store, regenerate on upsert |
| P6-T03 | `email_outbox` table + APScheduler worker with retry and backoff |
| P6-T04 | Post action queues one email per member with PDF attached |
| P6-T05 | Email log screen: sent / failed / retried, per batch |
| P6-T06 | Download PDF from member portal |

**Exit criteria:** Posting a batch emails every affected member, and the log shows each delivery.
**Test pack:** TP-6

---

### Phase 7 — Circulars, notifications and tickets
**Goal:** The association-side features from the client's checklist.

| Task | Deliverable |
|---|---|
| P7-T01 | Circular compose (rich text + attachment), global or selected members |
| P7-T02 | Circular list on member portal, read receipts |
| P7-T03 | In-app notification bell: new bill, new circular, payment posted |
| P7-T04 | Payment reminder rule: outstanding older than N days, admin-triggered |
| P7-T05 | Complaint tickets — member raises, admin responds, status workflow |
| P7-T06 | Ticket list and filters for admin |

**Exit criteria:** A global circular and an individual ticket both complete end to end.
**Test pack:** TP-7

---

### Phase 8 — Hardening and deployment
**Goal:** Production on OVH, and TALCO able to run a month unaided.

| Task | Deliverable |
|---|---|
| P8-T01 | Nginx + Let's Encrypt, HTTPS redirect, security headers |
| P8-T02 | Nightly `pg_dump` backup + documented restore drill |
| P8-T03 | Structured logging, error alerting to email |
| P8-T04 | Rate limiting on login, account lockout |
| P8-T05 | Admin operations manual (one page, Tanglish where it helps) |
| P8-T06 | UAT with TALCO office — full September cycle imported by their staff |
| P8-T07 | Handover: credentials, runbook, source, 30-day support window |

**Exit criteria:** TALCO staff import and dispatch a month without Smartiva touching the server.
**Test pack:** TP-8 — full regression, all packs re-run

---

## 4. Acceptance data — August 2026

These are the exact figures the system must reproduce. They are the project's contract with reality.

### Billing (sales vouchers 215–275 / 2026-2027)
| Charge head | GST | Vouchers | Base ₹ | CGST ₹ | SGST ₹ | Gross ₹ |
|---|---:|---:|---:|---:|---:|---:|
| Treatment charges | 5% | 37 | 43,24,121 | 1,08,109 | 1,08,109 | 45,40,339 |
| Chrome water | 5% | 8 | 1,15,600 | 2,890 | 2,890 | 1,21,380 |
| Sludge disposal | 18% | 16 | 83,694 | 7,532 | 7,532 | 98,758 |
| **Total** | | **61** | **45,23,415** | | | **47,60,477** |

### Receipts
| Metric | Value |
|---|---|
| Receipt vouchers | 53 |
| Distinct tanneries | 32 |
| Total | ₹57,66,381 |
| STEP-suffixed parties | 6 |

### Master
| Pump house | Tanneries |
|---|---|
| A | 10 |
| B | 8 |
| C | 15 |
| D | 5 |
| E | 2 |
| **Total** | **40** |

### Known data conditions the system must handle, not crash on
| Condition | Detail |
|---|---|
| Tanneries with no August bill | S.No 33, 36, 37 |
| Tanneries with no August receipt | S.No 1, 9, 13, 25, 35, 36, 37, 39 |
| Receipt but no bill | S.No 33 — ₹2,35,000 STEP receipt, zero billing |
| Expired TNPCB consent | 7 tanneries |
| Master GSTIN disagrees with Tally | 4 tanneries, one containing a Greek capital Ζ |
| Master GSTIN blank | 6 tanneries |
| C/o direction reversed | Irwin, Gautham, S.K. Leather — tannery sits **before** C/o |

---

## 5. Dependencies on the client

Two blockers that must be cleared before Phase 3 starts.

| # | Ask | Why |
|---|---|---|
| C1 | Add `DBCVCHNO` to the Tally XML export template | The voucher number is the idempotency key. Without it, a re-upload cannot be distinguished from a genuine second bill. |
| C2 | Add `DBCLEDNAME` per amount line | Identifies the charge head from the file itself, instead of relying on the admin's dropdown. |
| C3 | Confirm sludge disposal is correctly at 18% while treatment and chrome are at 5% | Affects the tax assertion in P1-T05. |
| C4 | Decide whether `-STEP` collections appear in the member's statement as a separate column or merged | Affects P5-T06 layout. |
| C5 | Supply the TALCO letterhead and the invoice format currently issued from Tally | Needed for P6-T01. |

---

## 6. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Tally export template cannot be changed | High — breaks idempotency | Fall back to `sha1(date+party+amount+row_index)` per batch, plus the file hash guard |
| New ledger names every month | Medium — admin fatigue | Alias table absorbs each name permanently after one approval |
| A mapping error bills the wrong member | Critical | No auto-post on fuzzy match, ever (rule G3) |
| Lessee sees owner's data | Critical | Single `scoped_query()` chokepoint + negative security tests in TP-5 |
| WeasyPrint fails only in production | Medium | System libraries in the Dockerfile from Phase 0, PDF smoke test in CI |
| Scope creep beyond the 56-point checklist | High — fixed budget | Any new item is a written change request against this plan |

---

## 7. Definition of done, per phase

A phase is complete only when **all four** are true:

1. All tasks in the phase table are marked Done in the tracker.
2. The phase's automated tests pass.
3. The phase's manual UI test pack passes with zero Critical or High defects open.
4. The tracker's phase row carries a completion date and a sign-off name.
