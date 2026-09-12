# TALCO CETP Member Portal — Manual UI Testing Guide

**Project:** TALCO Dindigul CETP Member Portal
**Version:** 1.0
**Purpose:** Run at the end of every phase, before that phase is signed off in the tracker.

---

## How to run a test pack

1. Start from a **clean known state** — the pack tells you which one.
2. Follow the steps exactly, in order. Do not skip a step because "it obviously works".
3. Record `PASS` / `FAIL` in the Result column and the date.
4. Any `FAIL` becomes a defect row in tracker §D with a severity.
5. A phase cannot be signed off with a **Critical** or **High** defect open.
6. Re-run the whole pack after fixes, not just the failed step — fixes break neighbours.

### Test data accounts to create once (Phase 5 onward)

| Login | Role | Linked to |
|---|---|---|
| `admin@talco.test` | talco_admin | — |
| `staff@talco.test` | talco_staff | — |
| `owner1@test` | member | S.No 29 Vaigai Leather Corporation |
| `owner2@test` | member | S.No 4 Meenakshi & Co |
| `lessee1@test` | lessee | Party "L.M.S Leathers" on S.No 4 |
| `lessee2@test` | lessee | Party "Asian Leathers" on S.No 31 |

`owner2` and `lessee1` are deliberately on the **same tannery** — that pair is what proves the scope rules.

### Severity guide
| Severity | Meaning |
|---|---|
| Critical | Wrong money, data loss, or one member seeing another's data |
| High | A phase's core function does not work |
| Medium | Wrong behaviour but a workaround exists |
| Low | Cosmetic, wording, alignment |

---

# TP-0 · Project setup

**Precondition:** fresh clone, `.env` filled from `.env.example`.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 0.1 | Run `docker compose up -d` | All three containers reach `healthy` | | |
| 0.2 | Open the API `/health` in a browser | JSON with `status: ok` and database reachable | | |
| 0.3 | Open the web URL | Page renders, Tailwind styling visible, no console errors | | |
| 0.4 | Stop postgres, reload `/health` | Returns an error clearly naming the database, not a blank 500 | | |
| 0.5 | Restart postgres, reload | Recovers without restarting the API | | |
| 0.6 | Run `pytest` | Green | | |
| 0.7 | Check `tests/fixtures/` | 4 XML + 5 workbook files present | | |

---

# TP-1 · Importer core library

**No UI in this phase.** Run from the terminal. This is the pack that decides whether the project works.

**Precondition:** `pytest -v` from the `api/` directory.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 1.1 | Load the five pump-house workbooks | 40 tanneries returned | | |
| 1.2 | Count by pump house | A=10, B=8, C=15, D=5, E=2 | | |
| 1.3 | Parse `Treatment.xml` | 37 rows · base **43,24,121** · gross **45,40,339** | | |
| 1.4 | Parse `Chrome.xml` | 8 rows · base **1,15,600** · gross **1,21,380** | | |
| 1.5 | Parse `Sludge.xml` | 16 rows · base **83,694** · gross **98,758** | | |
| 1.6 | Parse `Receipt.xml` | 53 rows · total **57,66,381** | | |
| 1.7 | Detected GST rate per file | Treatment 5%, Chrome 5%, Sludge 18% | | |
| 1.8 | Resolve all four files | **Zero** rows in the queue | | |
| 1.9 | Receipts grouped by tannery | 32 distinct tanneries | | |
| 1.10 | `L.M.S Leathers C/o. Meenakshi & Co` | Tannery = S.No 4, lessee = L.M.S Leathers | | |
| 1.11 | `IRWINTANNING COMPANY C/o. Sree Rajeshwari Leathers` | Tannery = S.No 32 — tannery is **before** C/o | | |
| 1.12 | `GAUTHAM LEATHER INDUSTRIES C/O, HAJI JAMAL MOHAMED` | Tannery = S.No 19 — comma separator handled | | |
| 1.13 | `Vaigai Leather Corporation A-Unit-STEP` | Tannery = S.No 29, `is_step = true` | | |
| 1.14 | `Vaigai Leather Corporation A-Unit` | Same tannery, `is_step = false` | | |
| 1.15 | Feed a row with `cgst != sgst` | Reported as a tax error, not resolved | | |
| 1.16 | Feed an unknown name `"Xyz Leathers C/o. Abc Tannery"` | Goes to queue with 3 ranked suggestions | | |
| 1.17 | Attempt to make a fuzzy suggestion auto-resolve | Impossible — `suggest()` returns ordering only | | |
| 1.18 | Feed a truncated / corrupt XML | Clear parse error naming the block, no crash | | |

**Gate:** every row PASS. A single FAIL here stops the project until fixed.

---

# TP-2 · Database and master load

**Precondition:** empty database, migrations applied, master import run once.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 2.1 | Log in as `admin@talco.test`, open Tanneries | 40 rows listed | | |
| 2.2 | Filter pump house = A | 10 rows, starting with Saddique Leathers A Unit | | |
| 2.3 | Filter pump house = E | 2 rows — S.M.A. Tanners, Sri Annai Abirami Tannery | | |
| 2.4 | Open S.No 29 Vaigai Leather Corporation | GPS, GST, consent date, capacity, shares all populated | | |
| 2.5 | Search by partial name "vaigai" | Both A and B units returned | | |
| 2.6 | Open the data-quality report | 4 GSTIN mismatches, 6 blank GSTINs, 7 expired consents | | |
| 2.7 | Check S.K. Leather Corporation in the report | Flagged — master contains a Greek Ζ instead of Z | | |
| 2.8 | Edit a tannery phone number and save | Saved, and an audit entry records who changed it | | |
| 2.9 | Re-run the master import command | No duplicates — still 40 rows | | |
| 2.10 | Log in as `staff@talco.test`, open a tannery | Read only — Edit button absent, not merely disabled | | |
| 2.11 | Call the master edit API directly with a staff token | 403 | | |
| 2.12 | View a tannery with no GST on screen | Shows a clear dash or "Not on record", never `None` or blank | | |

---

# TP-3 · Import pipeline

**Precondition:** Phase 2 passed. No batches imported yet.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 3.1 | Open Imports → New, upload `Treatment.xml` | Form asks charge head + period + source type before accepting | | |
| 3.2 | Submit without selecting a charge head | Validation error naming the field | | |
| 3.3 | Submit with charge head = Treatment, period = Aug 2026 | Batch created, status `parsed` | | |
| 3.4 | Open the batch review screen | 37 rows · 37 matched · 0 queued | | |
| 3.5 | Check the totals shown | Base **43,24,121** · CGST **1,08,109** · SGST **1,08,109** · Gross **45,40,339** | | |
| 3.6 | Check the tax verification line | "Tax check passed — 37 of 37 rows" | | |
| 3.7 | Press Post | Batch becomes `posted`, 37 invoices created | | |
| 3.8 | Upload `Treatment.xml` again, unchanged | Rejected: "already imported as batch #1 on <date>" | | |
| 3.9 | Import `Chrome.xml`, `Sludge.xml`, `Receipt.xml` the same way | All post cleanly, totals per plan §4 | | |
| 3.10 | Open the invoice list, filter Aug 2026 | 61 invoices, grand total **47,60,477** | | |
| 3.11 | Open the receipt list | 53 receipts, total **57,66,381** | | |
| 3.12 | Edit one amount in a copy of `Treatment.xml`, re-upload | Accepted (different hash), upsert on voucher no, revision row written | | |
| 3.13 | Open that invoice's history | Old and new amount both visible with timestamps | | |
| 3.14 | Check staging rows for batch #1 | Still present after posting | | |
| 3.15 | Upload a file with one deliberately unknown party | Batch posts the rest, status `partially_posted`, 1 row queued | | |
| 3.16 | Log in as `staff@talco.test` and try to Post a batch | Upload allowed, Post button absent, API returns 403 | | |
| 3.17 | Interrupt a post (kill the API mid-transaction) | Nothing partially written — batch still unposted on restart | | |

---

# TP-4 · Mapping queue

**Precondition:** Phase 3 passed, one queued row from step 3.15.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 4.1 | Open Mapping Queue | The queued row is listed with its batch reference | | |
| 4.2 | Inspect the row | Raw name, both split sides, and 3 ranked suggestions shown | | |
| 4.3 | Confirm the suggestions are sensible | Closest tannery name appears first | | |
| 4.4 | Choose "Link to existing tannery", pick the right tannery | Asks for role (owner / lessee) and `valid_from` | | |
| 4.5 | Check `valid_from` default | Pre-filled with the batch period start date | | |
| 4.6 | Save the link | Row leaves the queue, batch moves to `posted` | | |
| 4.7 | Open the tannery detail | The new lessee appears under linked parties with its date | | |
| 4.8 | Re-upload the same file | That name auto-matches — match method shows `alias` | | |
| 4.9 | Open Alias management | The new alias is listed with who approved it and when | | |
| 4.10 | Revoke the alias, re-upload | The name is back in the queue | | |
| 4.11 | Use "Not a member" on a test row | Excluded, counted in the batch summary, not posted | | |
| 4.12 | Log in as `staff@talco.test`, open the queue | Visible read-only; link and exclude actions absent, API returns 403 | | |
| 4.13 | Try to link a name to two tanneries at once | Prevented with a clear message | | |

---

# TP-5 · Auth, RBAC and portal ⚠️ security-critical

**Precondition:** August data posted, all six test accounts created.

## 5A · Login and account

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 5.1 | Log in with a wrong password five times | Account locks or rate limits with a clear message | | |
| 5.2 | Use the password reset link | Email received, link works once, second use rejected | | |
| 5.3 | First login by an invited member | Forced to set a password before reaching any data | | |
| 5.4 | Log out, press browser Back | Returns to login, not a cached portal page | | |
| 5.5 | Leave a session idle past the timeout | Next action redirects to login | | |

## 5B · Owner scope

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 5.6 | Log in as `owner1@test` (Vaigai, S.No 29) | Dashboard shows only Vaigai A Unit | | |
| 5.7 | Check the outstanding figure | Matches invoices minus receipts for that tannery |  | |
| 5.8 | Open the ledger | Invoices and receipts interleaved by date with a running balance | | |
| 5.9 | Check STEP receipts appear | ₹1,65,000 STEP receipt visible and labelled | | |
| 5.10 | Verify the running balance by hand for 5 rows | Matches exactly | | |
| 5.11 | Log in as `owner2@test` (Meenakshi & Co, S.No 4) | Sees the invoice billed to lessee L.M.S Leathers — it is against his premises | | |
| 5.12 | Check consent status on the dashboard | Meenakshi & Co shows **Expired 31.03.2024** in a warning state | | |

## 5C · Lessee scope

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 5.13 | Log in as `lessee1@test` (L.M.S Leathers on S.No 4) | Sees only vouchers billed to L.M.S Leathers | | |
| 5.14 | Check the tannery name is shown | Meenakshi & Co displayed as context | | |
| 5.15 | Look for the owner's other data | Owner's shares, other parties, other arrears — **none visible** | | |
| 5.16 | Compare the ledger with `owner2@test` | Lessee's list is a strict subset | | |

## 5D · Negative security tests — all must fail closed

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 5.17 | As `lessee1`, change the tannery id in the URL to 29 | **403**, not another member's page | | |
| 5.18 | As `lessee1`, call the ledger API with `party_id` of another party | **403** | | |
| 5.19 | As `lessee1`, request an invoice PDF belonging to another party | **403** | | |
| 5.20 | As `owner1`, open a tannery he is not linked to | **403** | | |
| 5.21 | As `owner1`, open any admin route | **403** | | |
| 5.22 | Copy `lessee1`'s token, call an admin endpoint | **403** | | |
| 5.23 | Call any portal endpoint with no token | **401** | | |
| 5.24 | Call with an expired token | **401** | | |
| 5.25 | Search or filter fields on the member portal | No parameter widens scope beyond the user's own rows | | |

**Any FAIL in 5D is Critical and blocks the phase outright.**

---

# TP-6 · Invoice PDF and email

**Precondition:** Phase 5 passed, SMTP configured to a test inbox.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 6.1 | Open invoice 216/2026-2027 (Saddique Leathers A) | PDF renders, no missing fonts or blank boxes | | |
| 6.2 | Check the header | TALCO name, address, GSTIN `33AAACT2664C1ZS` | | |
| 6.3 | Check the party block | Ledger name and GSTIN as billed, not the master's version | | |
| 6.4 | Check the amounts | Base 96,300 · CGST 2,408 · SGST 2,408 · Gross 1,01,116 | | |
| 6.5 | Check a sludge invoice | 9% + 9%, correct SAC code | | |
| 6.6 | Check amount in words | Correct at lakh scale, ends with "only" | | |
| 6.7 | Print the PDF | Fits A4, nothing clipped at the margins | | |
| 6.8 | Post a batch | One email queued per affected member | | |
| 6.9 | Open the test inbox | Email received with the PDF attached, subject names the month | | |
| 6.10 | Check a member with three charge heads | Receives all three invoices, not just one | | |
| 6.11 | Break the SMTP password, post a batch | Outbox shows failed, retries with backoff, log states the reason | | |
| 6.12 | Restore SMTP | Queued emails go out on the next worker run without a re-post | | |
| 6.13 | Re-import a corrected voucher | PDF regenerated, member notified that the amount changed | | |
| 6.14 | Download the PDF from the member portal as `owner1` | Works | | |
| 6.15 | Try that PDF URL as `lessee2` | **403** | | |

---

# TP-7 · Circulars, notifications and tickets

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 7.1 | Admin composes a global circular with a PDF attachment | Sent to all 40 members | | |
| 7.2 | Log in as `owner1` | Circular visible with attachment downloadable | | |
| 7.3 | Check read receipts on the admin side | `owner1` marked read, others unread | | |
| 7.4 | Send a circular to 3 selected members | Only those 3 see it; a fourth member does not | | |
| 7.5 | Post a new batch | Notification bell increments for affected members only | | |
| 7.6 | Trigger payment reminders for outstanding > 30 days | Only genuinely overdue members receive one | | |
| 7.7 | `owner1` raises a ticket | Appears in the admin ticket list as Open | | |
| 7.8 | Admin replies and sets In Progress | Member sees the reply and the new status | | |
| 7.9 | Admin resolves, member closes | Status workflow completes | | |
| 7.10 | `owner2` opens the ticket list | Cannot see `owner1`'s ticket | | |
| 7.11 | Attempt to open another member's ticket by id | **403** | | |

---

# TP-8 · Pre-release regression

Run everything, on the production server, with production configuration.

| # | Step | Expected | Result | Date |
|---|---|---|---|---|
| 8.1 | Re-run TP-0 through TP-7 on production | All green | | |
| 8.2 | Open the site over HTTP | Redirects to HTTPS | | |
| 8.3 | Check the certificate | Valid, correct domain, not expiring within 30 days | | |
| 8.4 | Take a `pg_dump`, restore into a scratch database | Restores cleanly; row counts match | | |
| 8.5 | Query the scratch database | 40 tanneries, 61 August invoices, 53 receipts | | |
| 8.6 | Open the portal on a phone (~400px) | Ledger table scrolls horizontally; page does not | | |
| 8.7 | Open the admin import screen on a tablet | Usable, no overlapping controls | | |
| 8.8 | Test on Chrome, Edge and mobile Safari | Consistent behaviour | | |
| 8.9 | Force a 500 error | Friendly message shown; stack trace not exposed to the user | | |
| 8.10 | Check the error alert email | Received by the admin address | | |
| 8.11 | TALCO staff import September unaided, observed only | Completes without Smartiva touching anything | | |
| 8.12 | Ask the TALCO operator to state what each screen does | Matches the operations manual | | |

---

## Sign-off record

| Test pack | Run by | Date | Result | Defects raised | Retest date | Final |
|---|---|---|---|---|---|---|
| TP-0 | | | | | | |
| TP-1 | | | | | | |
| TP-2 | | | | | | |
| TP-3 | | | | | | |
| TP-4 | | | | | | |
| TP-5 | | | | | | |
| TP-6 | | | | | | |
| TP-7 | | | | | | |
| TP-8 | | | | | | |

**Project accepted by (TALCO):** ____________________  **Date:** ____________

**Delivered by (Smartiva Technologies LLP):** ____________________  **Date:** ____________
