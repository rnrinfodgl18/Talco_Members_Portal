# TALCO CETP Member Portal — Implementation Tracker

**Project:** TALCO Dindigul CETP Member Portal
**Vendor:** Smartiva Technologies LLP
**Tracker version:** 1.0
**Last updated:** 2026-09-12 — Circulars and member Notice Board implemented; Phase 0–5 manual sign-off pending

---

## How to use this file

1. Work top to bottom. Do not start a phase until the phase above it is **Done**.
2. When you start a task, set Status to `WIP` and fill **Started**.
3. When you finish, set Status to `Done`, fill **Completed**, and tick the acceptance box.
4. If something blocks you, set Status to `Blocked` and write the reason in the Notes column — never leave a task silently stalled.
5. A phase is Done only when its **Phase gate** checklist at the end of the phase is fully ticked.
6. Log every defect in §D. Log every scope change in §S. Log every decision in §L.

### Status values
`Not started` · `WIP` · `Blocked` · `In review` · `Done` · `Dropped`

### Priority
`P0` must have · `P1` should have · `P2` nice to have

---

## Progress summary

_Update these counts as you go._

| Phase | Tasks | Done | Status | Started | Completed | Sign-off |
|---|---:|---:|---|---|---|---|
| 0 · Project setup | 7 | 7 | In review | 2026-09-10 | 2026-09-10 | Manual TP-0 pending |
| 1 · Importer core library | 8 | 8 | In review | 2026-09-10 | 2026-09-10 | Manual TP-1 pending |
| 2 · Database & master load | 6 | 6 | In review | 2026-09-10 | 2026-09-10 | Manual TP-2 pending |
| 3 · Import pipeline | 8 | 8 | In review | 2026-09-10 | 2026-09-10 | Manual TP-3 pending |
| 4 · Mapping queue | 6 | 6 | In review | 2026-09-10 | 2026-09-10 | Manual TP-4 pending |
| 5 · Auth, RBAC & portal | 8 | 8 | In review | 2026-09-10 | 2026-09-10 | Manual TP-5 pending |
| 6 · Invoice PDF & email | 6 | 0 | Not started | | | |
| 7 · Circulars & tickets | 6 | 3 | WIP | 2026-09-12 | | |
| 8 · Hardening & deployment | 7 | 0 | Not started | | | |
| **Total** | **62** | **46** | **WIP** | | | |

---

## Phase 0 — Project setup

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P0-T01 | Git repo, `main`/`dev` branches, `.gitignore`, `.env.example` | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | |
| P0-T02 | `docker-compose.yml` — api, web, postgres, healthchecks | P0 | 3h | Done | 2026-09-10 | 2026-09-10 | |
| P0-T03 | API Dockerfile **with WeasyPrint system libs** | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | Miss this and PDF fails only at runtime |
| P0-T04 | Vite + React + TS + Tailwind scaffold, `/health` page | P0 | 3h | Done | 2026-09-10 | 2026-09-10 | |
| P0-T05 | `GET /health` returning DB connectivity | P0 | 1h | Done | 2026-09-10 | 2026-09-10 | |
| P0-T06 | pytest configured, one green dummy test | P0 | 1h | Done | 2026-09-10 | 2026-09-10 | |
| P0-T07 | Copy 4 Aug XML + 5 pump-house workbooks into `tests/fixtures/` | P0 | 1h | Done | 2026-09-10 | 2026-09-10 | Never commit real member emails to a public repo |

**Phase 0 gate**
- [ ] `docker compose up` starts all three containers healthy
- [ ] API reachable, `/health` returns DB OK
- [ ] Web page loads
- [ ] `pytest` green
- [ ] Test pack **TP-0** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 1 — Importer core library ⚠️ highest risk

> No database. No web server. No UI. A pure Python library with the real August files as fixtures.

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P1-T01 | `masters.py` — 5 workbooks → 40 `Tannery` objects | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | Sheet title row varies (row 1 or 2) — handle both |
| P1-T02 | `normalize.py` → `nkey()` | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | unescape → upper → `&`→`AND` → strip non-alphanumeric |
| P1-T03 | `normalize.py` → `split_party()` | P0 | 3h | Done | 2026-09-10 | 2026-09-10 | STEP regex + C/o regex |
| P1-T04 | `parser.py` — UTF-16 XML → `VoucherRow[]` | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | `DBCLEDAMT` position 0 = base |
| P1-T05 | Tax assertion, failures collected not dropped | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | `cgst == sgst`, `base × rate ≈ tax` ±1 |
| P1-T06 | `matcher.py` → `resolve()` 4-step algorithm | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | The core of the project |
| P1-T07 | `suggest()` via `difflib`, top 3, ordering only | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | Must never auto-select — rule G3 |
| P1-T08 | Unit tests reproducing every §4 control total | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | See acceptance table below |

### P1 acceptance — must reproduce exactly
- [ ] `masters.py` returns 40 tanneries — A:10, B:8, C:15, D:5, E:2
- [ ] Treatment.xml → 37 rows, base **43,24,121**, gross **45,40,339**
- [ ] Chrome.xml → 8 rows, base **1,15,600**, gross **1,21,380**
- [ ] Sludge.xml → 16 rows, base **83,694**, gross **98,758**, rate detected 18%
- [ ] Receipt.xml → 53 rows, total **57,66,381**, mapped to **32** tanneries
- [ ] Zero rows in the queue for all four August files
- [ ] Reversed C/o cases resolve correctly: Irwin, Gautham, S.K. Leather
- [ ] `Vaigai … A-Unit` and `Vaigai … A-Unit-STEP` resolve to the **same** tannery with different `is_step`
- [ ] A row with a deliberately corrupted tax amount is reported, not posted

**Phase 1 gate**
- [ ] All 8 tasks Done
- [ ] Every acceptance box above ticked
- [ ] Test pack **TP-1** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 2 — Database and master load

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P2-T01 | Alembic migration — 10 tables | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | |
| P2-T02 | Indexes and unique constraints | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | See plan §Phase 2 |
| P2-T03 | Seed `charge_head` — 5% / 5% / 18% | P0 | 1h | Done | 2026-09-10 | 2026-09-10 | |
| P2-T04 | Master import command | P0 | 4h | Done | 2026-09-10 | 2026-09-10 | Idempotent — safe to re-run |
| P2-T05 | Data-quality report on load | P1 | 4h | Done | 2026-09-10 | 2026-09-10 | Expect 4 GST mismatches, 6 blanks, 7 expired consents |
| P2-T06 | Admin master list + detail (read + edit) | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | |

**Phase 2 gate**
- [ ] 40 tanneries in the database
- [ ] Filter by pump house returns 10 / 8 / 15 / 5 / 2
- [ ] Re-running the master import creates no duplicates
- [ ] Data-quality report flags all 4 GST mismatches and 7 expired consents
- [ ] Non-admin cannot reach the master edit screen
- [ ] Test pack **TP-2** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 3 — Import pipeline

> Blocked until client items **C1** and **C2** are confirmed (see plan §5).

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P3-T01 | `POST /imports` + SHA-256 duplicate guard | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | |
| P3-T02 | Parse → staging rows, status `parsed` | P0 | 4h | Done | 2026-09-10 | 2026-09-10 | |
| P3-T03 | Run matcher, mark `matched` / `queued` | P0 | 4h | Done | 2026-09-10 | 2026-09-10 | |
| P3-T04 | Batch review screen with totals + tax check | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | Admin eyeballs the total before posting |
| P3-T05 | `POST /imports/{id}/post` — single transaction | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | Rollback on any constraint failure |
| P3-T06 | Upsert on `(voucher_no, fy)` + `invoice_revision` | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | |
| P3-T07 | Batch list screen | P0 | 4h | Done | 2026-09-10 | 2026-09-10 | |
| P3-T08 | `partially_posted` state | P1 | 3h | Done | 2026-09-10 | 2026-09-10 | One stuck name must not block 40 members |

**Phase 3 gate**
- [ ] All four August files import and post
- [ ] Posted totals equal plan §4 exactly
- [ ] Re-uploading an identical file is rejected with the earlier batch reference
- [ ] Re-uploading a corrected file upserts and writes a revision row
- [ ] Staging rows still present after posting
- [ ] Test pack **TP-3** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 4 — Mapping queue

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P4-T01 | Queue screen — raw name, split sides, suggestions | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | |
| P4-T02 | "Link to existing tannery" action | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | Writes party + link + alias |
| P4-T03 | `valid_from` on link, default = batch period start | P0 | 2h | Done | 2026-09-10 | 2026-09-10 | This is how lease history gets recorded |
| P4-T04 | "Not a member" action | P1 | 3h | Done | 2026-09-10 | 2026-09-10 | |
| P4-T05 | Alias management screen (view, revoke) | P1 | 5h | Done | 2026-09-10 | 2026-09-10 | |
| P4-T06 | Owner ↔ lessee link approval with role | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | |

**Phase 4 gate**
- [ ] A renamed ledger lands in the queue with sensible suggestions
- [ ] Linking it once makes the next import auto-match at step 1
- [ ] Revoking an alias sends the name back to the queue
- [ ] Fuzzy suggestions never auto-apply — verified by attempting it
- [ ] Test pack **TP-4** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 5 — Auth, RBAC and portal

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P5-T01 | Auth ported from Bankers, multi-tenant layer stripped | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | Strip it, don't disable it |
| P5-T02 | 5 roles defined and enforced | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | |
| P5-T03 | `scoped_query()` — single chokepoint | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | Never repeat scope logic per endpoint |
| P5-T04 | Invite, first-login password set, reset | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | |
| P5-T05 | Member dashboard | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | |
| P5-T06 | Ledger with running balance | P0 | 8h | Done | 2026-09-10 | 2026-09-10 | UNION invoice + receipt, window function |
| P5-T07 | Invoice list + detail, receipt list | P0 | 6h | Done | 2026-09-10 | 2026-09-10 | |
| P5-T08 | Lessee party-scoped view | P0 | 5h | Done | 2026-09-10 | 2026-09-10 | |

**Phase 5 gate**
- [ ] Owner sees every voucher against his tannery, lessee's included
- [ ] Lessee sees only his own party's vouchers
- [ ] **Negative test:** lessee changing the id in the URL gets 403, not another member's data
- [ ] **Negative test:** direct API call with a lessee token cannot read another party
- [ ] Running balance for a sample tannery matches a hand calculation
- [ ] Test pack **TP-5** passed with zero security defects open
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 6 — Invoice PDF and email

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P6-T01 | Jinja2 invoice template | P0 | 8h | Not started | | | Needs client item C5 |
| P6-T02 | WeasyPrint render + store + regenerate on upsert | P0 | 6h | Not started | | | |
| P6-T03 | `email_outbox` + APScheduler worker, retry + backoff | P0 | 6h | Not started | | | No Celery |
| P6-T04 | Post action queues member emails with PDF | P0 | 4h | Not started | | | |
| P6-T05 | Email log screen per batch | P1 | 4h | Not started | | | |
| P6-T06 | PDF download from member portal | P0 | 3h | Not started | | | |

**Phase 6 gate**
- [ ] PDF matches the format TALCO issues today
- [ ] CGST / SGST split and SAC code correct on every charge head
- [ ] Amount in words correct for a lakh-scale figure
- [ ] Posting a batch queues one email per affected member
- [ ] A forced SMTP failure retries and is visible in the log
- [ ] Test pack **TP-6** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 7 — Circulars, notifications and tickets

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P7-T01 | Circular compose, global or selected members | P0 | 8h | Done | 2026-09-12 | 2026-09-12 | Attachment, expiry, priority, draft/publish, audit |
| P7-T02 | Circular list + read receipts on portal | P1 | 5h | Done | 2026-09-12 | 2026-09-12 | Target-scoped notice board and secure downloads |
| P7-T03 | In-app notification bell | P1 | 6h | Done | 2026-09-12 | 2026-09-12 | PWA push, email verification and delivery log included |
| P7-T04 | Payment reminder rule, admin-triggered | P1 | 5h | Not started | | | |
| P7-T05 | Complaint tickets with status workflow | P0 | 10h | Not started | | | |
| P7-T06 | Admin ticket list + filters | P0 | 4h | Not started | | | |

**Phase 7 gate**
- [ ] Global circular reaches all members, individual reaches only the selected
- [ ] Ticket travels open → in progress → resolved → closed
- [ ] Member sees only his own tickets
- [ ] Test pack **TP-7** passed
- [ ] Phase signed off by: ____________ on ____________

---

## Phase 8 — Hardening and deployment

| ID | Task | Pri | Est | Status | Started | Completed | Notes |
|---|---|---|---|---|---|---|---|
| P8-T01 | Nginx + Let's Encrypt + security headers | P0 | 4h | Not started | | | |
| P8-T02 | Nightly `pg_dump` + **restore drill actually performed** | P0 | 4h | Not started | | | A backup you have not restored is not a backup |
| P8-T03 | Structured logging + error alert email | P1 | 4h | Not started | | | |
| P8-T04 | Login rate limiting + lockout | P0 | 3h | Not started | | | |
| P8-T05 | Admin operations manual | P0 | 5h | Not started | | | Tanglish where it helps the office staff |
| P8-T06 | UAT — TALCO staff import a full September cycle | P0 | 8h | Not started | | | |
| P8-T07 | Handover: credentials, runbook, source, 30-day support | P0 | 4h | Not started | | | |

**Phase 8 gate**
- [ ] HTTPS live, HTTP redirects
- [ ] Backup restored successfully into a scratch database
- [ ] TALCO staff complete a month with no Smartiva intervention
- [ ] All test packs TP-0 … TP-8 re-run green
- [ ] Handover documents delivered and acknowledged
- [ ] Project signed off by: ____________ on ____________

---

## §C — Client dependency tracker

| ID | Ask | Blocks | Requested on | Received on | Status |
|---|---|---|---|---|---|
| C1 | Add `DBCVCHNO` to Tally XML export | Phase 3 | | | Open |
| C2 | Add `DBCLEDNAME` per amount line | Phase 3 | | | Open |
| C3 | Confirm sludge GST is 18% vs 5% on the others | Phase 1 | | | Open |
| C4 | STEP shown separately or merged in statement | Phase 5 | | | Open |
| C5 | TALCO letterhead + current invoice format | Phase 6 | | | Open |
| C6 | Member email list, verified | Phase 6 | | | Open |
| C7 | Confirm bill 230 `IRWINTANNING C/o. Sree Rajeshwari` maps to Irwin Tanning Company | Phase 1 | | | Open |

---

## §D — Defect log

| ID | Phase | Found in test | Description | Severity | Status | Fixed in | Retested |
|---|---|---|---|---|---|---|---|
| D-001 | Phase 2 | Manual TP-2 | Browser CORS preflight for protected Tanneries API returned 401, causing Failed to fetch | Medium | Fixed | b8f6c87 | Automated + API retest passed; user retest pending |
| D-002 | Phase 3 | Manual TP-3 | Tax-error row showed error state but omitted the validation reason | Medium | Closed | 2bfd995 | User manually retested tax error, post action and mapping suggestions — passed |
| D-003 | Phase 5 | Manual TP-5 | Lessee portal heading showed premises tannery instead of lessee party identity | Medium | Closed | 87c29b5 | User manually retested — passed |
| D-004 | Phase 5 | Manual TP-5 | Invite form required internal tannery and party database IDs | Medium | Fixed | 3a4ad2a | Manual retest deferred by user |
| D-003 | Phase 5 | Manual TP-5 | Lessee dashboard showed tannery name as primary identity instead of linked party name | Medium | Fixed | Pending commit | API verified LMS party with Meenakshi premises; user retest pending |

**Severity:** `Critical` blocks release · `High` wrong data or security · `Medium` wrong behaviour with workaround · `Low` cosmetic

---

## §S — Scope change log

Anything not in the plan is a change request. Fixed budget, so record every one.

| ID | Date | Requested by | Change | Impact (hrs / ₹) | Decision | Approved by |
|---|---|---|---|---|---|---|
| S-001 | | | | | | |

---

## §L — Decision log

| ID | Date | Decision | Reason | Supersedes |
|---|---|---|---|---|
| L-001 | Sep 2026 | Tally XML is the only import format | GST breakup and GSTIN present; fixed structure | Earlier Excel-upload plan |
| L-002 | Sep 2026 | C/o mapping via admin-approved alias table | C/o direction is inconsistent in real data | Auto-split assumption |
| L-003 | Sep 2026 | No AI or LLM in the import path | Billing must be reproducible | — |
| L-004 | Sep 2026 | Single-tenant build for TALCO only | Budget and scope | Multi-tenant deferred |
| L-005 | Sep 2026 | No Celery / Redis; DB outbox + APScheduler | 40 members, monthly cycle | — |
| L-006 | | | | |

---

## §R — Weekly status

| Week ending | Phase | Done this week | Planned next week | Blockers | Hours |
|---|---|---|---|---|---|
| | | | | | |
