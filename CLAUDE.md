# TALCO-DINTEC Member Portal — Development Handoff

Last updated: 21 September 2026
Stable Git commit: 1764806
Branch: codex/dintec-demo-ui
Repository: https://github.com/rnrinfodgl18/Talco_Members_Portal
Production: https://talco.smartiva.tech
VPS: smartiva@100.73.142.127 through Tailscale
VPS path: /home/smartiva/office/projects/8002-talco-dintec

This is the single current handoff document. Read it fully before editing or deploying. Older plans, status notes and manuals are stored under Archive/.

## 1. Product purpose

TALCO-DINTEC is a mobile-first member portal for CETP administration. Tally or Excel monthly imports are the accounting source. The portal provides Pump, Tannery and Ledger masters; multi-ledger access under one login; invoice/receipt imports; account statements; formal documents; circulars; notifications; and PWA access.

Do not invent financial data or add unsupported telemetry/payment features.

## 2. Technology and important files

Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, WeasyPrint and Pytest.

- api/app/main.py — application/router registration and health endpoint.
- api/app/models/ — database models.
- api/app/routers/ — API endpoints.
- api/app/services/import_parser.py — Excel/XML import parser.
- api/app/services/invoice_pdf.py — invoice_html builds the markup, invoice_pdf prints it. One layout serves both the PDF and the phone preview.
- api/app/services/scope.py — shared member/account access scoping, including the lessee lease window.
- api/app/services/notifications.py — email (with attachments) and push delivery.
- api/app/services/bill_dispatch.py — sends posted bills by email and WhatsApp.
- api/app/services/circular_audience.py — resolves a circular's recipients.
- api/app/services/whatsapp.py — FII Tech WhatsApp API.
- api/alembic/versions/ — migrations.
- api/tests/ — regression tests.

Frontend: React, TypeScript, Vite, Tailwind utilities, shared CSS tokens and PWA service worker.

- web/src/App.tsx — authenticated shell, navigation and session restore.
- web/src/DashboardPage.tsx — admin/member dashboards.
- web/src/PortalPage.tsx — ledger, invoices, receipts and PDF preview.
- web/src/ImportsPage.tsx — imports, correction review and bill dispatch.
- web/src/ReportsPage.tsx — admin outstanding summary.
- web/src/NotificationLogPage.tsx — delivery log, filters and the recipient drill-down.
- web/src/CircularChannels.tsx — circular delivery switches in Settings.
- web/src/CircularsPage.tsx — circular and notice board.
- web/src/SettingsPage.tsx — profile/company/SMTP/WhatsApp settings.
- web/src/styles.css — the interface kit. One :root owns every colour; .btn (three sizes, four variants) owns every button. Legacy cyan and teal mappings are gone because those classes no longer exist in any component; only the slate-to-token mappings remain, and they are a compatibility layer, not a place to add colours.
- web/src/theme.ts — admin-editable theme defaults. They must stay equal to the :root values in styles.css, since applyTheme writes the same custom properties at runtime.
- web/public/sw.js — PWA cache; current key talco-shell-v15.

## 3. Completed functionality

Authentication and users:

- Admin bootstrap, invitations and email-delivered setup links.
- Admin-issued accounts: username plus a password handed over in person, no email required. app_user.email is nullable.
- Forgot/reset password.
- Username, email or phone login.
- Username, display name, email and phone profile update.
- Email and WhatsApp phone verification.
- One-year rolling session keep-alive and PWA session restore.
- One login with multiple ledger-account access.
- Owner, lessee, account-holder and staff relationships.

Masters/accounts:

- Pump Master CRUD.
- Tannery Master CRUD with automatic serial number.
- Pump selection and Pump + Tannery Excel import.
- Ledger Master, opening amount/date/Dr-Cr/note.
- Opening-balance Excel review and approved overwrite.
- Calculated closing balance with Dr red and Cr green.

Tally/Excel imports:

- Excel-first .xlsx/.xlsm and Tally XML imports.
- Mixed Sales and Receipt vouchers.
- UTF-16/legacy XML cleanup.
- GUID/ALTERID identity and idempotent duplicates.
- Missing non-critical voucher/reference values produce warnings.
- Tax/total calculation where supported.
- Mapping queue with bind, unbind and rebind.
- Invoice correction detection with admin reason/approval.
- Revision/audit history, cancellation handling and receipt allocations.

Member portal/documents:

- Scoped ledger accounts and statements.
- Tally-style ledger print.
- Official invoice and receipt PDF endpoints.
- Invoice View opens the actual official PDF.
- Bank Receipt Voucher output.
- Tax Invoice now matches the supplied Tally layout: seller/buyer split, metadata grid, tall service table, HSN/SAC, base/CGST/SGST, total, amount in words, bank block, declaration and authorised signatory.
- Invoice bank details are stored on CompanySetting (bank_name, bank_account_number, bank_branch, bank_ifsc) and edited in Admin Settings. The bank block falls back to an em dash while a value is unset. Never hardcode values from a screenshot.
- Bank details are excluded from the unauthenticated /api/settings/public response.

Circulars/notifications:

- Draft/publish, expiry and deletion.
- Four audiences: all, hand-picked, role-wise (owners / lessees / member staff), and everyone with outstanding. The last three are resolved when the circular publishes and the resulting users are snapshotted into circular_recipient, so paying up afterwards never hides a notice already addressed. Visibility for every audience except "all" reads that snapshot.
- Audience preview shows the resolved count and names before publishing.
- PDF/image/Word/Excel attachments up to 8 MB and secured download.
- Read/unread, filters and pagination.
- Notification bell, notification pagination/read state.
- SMTP test and delivery logs.
- Published circulars go out on email and WhatsApp per the Circular delivery switches in Admin Settings. WhatsApp carries text and a portal link only, paced 8-15s apart; attachments stay in the portal.
- Notification Log is its own admin page with channel, status, type and recipient filters, and a per-item drill-down showing every recipient, each channel's outcome and read/unread.
- Web push subscriptions.
- WhatsApp API settings, test and phone verification.

UI/PWA:

- Separate admin and member dashboards.
- Last Sync on from latest posted import.
- Navy shell with a navy-anchored action palette: azure #1f5fd0 primary, jade #0b7a63 positive, clay #b42318 negative, amber #9a6100 pending. Each clears 4.5:1 against the text on it; the cyan they replaced sat at 1.81:1.
- Buttons come from .btn plus a size and a variant. Size is chosen by the weight of the action: btn-lg for the one thing a page exists to do, btn-md for form submits, btn-sm for a row action. Never write a bespoke padding-and-colour button.
- Dashboard metrics carry a toned icon, tabular numerals, and a severity stripe (.is-attention) on the one figure that needs a decision.
- Mobile drawer, bottom navigation and card-style tables.
- Installable PWA and persistent session.
- Binary endpoints go through apiBlob/saveBlob in web/src/api.ts. Never fetch an /api path without the apiUrl prefix, never click a detached anchor, and never revoke an object URL straight after the click: Android drops all three.
- A phone cannot render a PDF in an iframe, so invoices and receipts are saved to the device there and framed only on a wide screen.
- Push records why it did not deliver (no VAPID keys, or no device enabled), instead of failing silently.
- Theme Designer hidden; Help page removed.
- Footer credits FII Tech.in only.

## 4. Production baseline

Containers:

- talco-v1-postgres — internal database.
- talco-v1-api — internal API.
- talco-v1-web — Nginx gateway.
- Only 127.0.0.1:8002 is published.

Current migration: 0020_circular_audience_roles (head).

Latest verification:

- Backend: 120 tests passed.
- Frontend TypeScript/Vite production build passed.
- Tally invoice generated and rendered for visual A4 inspection.
- Production API/web/database containers healthy.
- Health response: status ok, database reachable.

## 5. Non-negotiable rules

1. Every member financial query must use the shared scope service/scoped-query path.
2. Never expose another member's account, tannery, invoice, receipt or ledger.
3. Imports must remain idempotent.
4. Never silently overwrite an existing invoice. Corrections require review, reason and audit.
5. Administrative financial/access changes must retain audit entries.
6. Never log, document or commit secrets.
7. Never overwrite the VPS .env file.
8. PostgreSQL and API remain internal; only the web gateway is published.
9. Keep globally unique container names on the shared office network.
9a. Never call .replace(tzinfo=...) on a value read from a DateTime(timezone=True)
   column. PostgreSQL returns it aware in the server zone, so replacing the
   offset shifts the value; use as_utc() in api/app/security.py.
10. Never delete production data for testing.
11. Do not commit the untracked output/ directory.
12. Preserve mobile/PWA behavior.
13. Increment the service-worker cache key when frontend assets must refresh.

## 6. Local development

Local path:

    D:\Projects\talco-dintec\webApp-v1

Start:

    docker compose up -d --build
    docker compose ps

Local web: http://localhost:5173
Local API: http://localhost:8000
Health: http://localhost:8000/health

Backend verification:

    docker compose build api
    docker compose run --rm api pytest -q

Current expected result: 120 passed.

Frontend verification:

    cd web
    npm install
    npm run build

Migration verification:

    docker compose run --rm api alembic upgrade head

The next migration must follow 0020_circular_audience_roles. Test every migration against PostgreSQL.

## 7. Git workflow

Current branch: codex/dintec-demo-ui
Stable commit: dd81a8a

GitHub privacy protection requires the repository-local no-reply email:

    rnrinfodgl18@users.noreply.github.com

Normal flow:

    git status --short
    git diff --check
    git add <specific files>
    git commit -m "clear message"
    git push origin HEAD

The local output/ folder is intentionally untracked.

## 8. VPS deployment

Connect:

    ssh smartiva@100.73.142.127
    cd /home/smartiva/office/projects/8002-talco-dintec

### Critical VPS Git warning

The VPS path is inside an old monorepo checkout. It reports many legacy modified/deleted files while the current api/ and web/ folders are untracked from that old repository view.

Do not run git reset --hard, git clean or normal git pull in the VPS project.

Use source-only archives.

Full release from Windows project root:

    tar --exclude=web/node_modules --exclude=web/dist --exclude=output --exclude=tmp -czf talco-release.tar.gz api web
    scp talco-release.tar.gz smartiva@100.73.142.127:/tmp/talco-release.tar.gz
    ssh smartiva@100.73.142.127 "cd /home/smartiva/office/projects/8002-talco-dintec && rm -rf web/node_modules web/dist && tar -xzf /tmp/talco-release.tar.gz && docker compose -f docker-compose.vps.yml up -d --build --wait && rm -f /tmp/talco-release.tar.gz"
    Remove-Item -LiteralPath .\talco-release.tar.gz -Force

Never copy Windows web/node_modules. It causes Linux build failure: tsc Permission denied.

API-only release:

    tar -czf talco-api-release.tar.gz api
    scp talco-api-release.tar.gz smartiva@100.73.142.127:/tmp/talco-api-release.tar.gz
    ssh smartiva@100.73.142.127 "cd /home/smartiva/office/projects/8002-talco-dintec && tar -xzf /tmp/talco-api-release.tar.gz && docker compose -f docker-compose.vps.yml up -d --build --wait talco-v1-api && rm -f /tmp/talco-api-release.tar.gz"

Web-only release:

    tar --exclude=web/node_modules --exclude=web/dist -czf talco-web-release.tar.gz web
    scp talco-web-release.tar.gz smartiva@100.73.142.127:/tmp/talco-web-release.tar.gz
    ssh smartiva@100.73.142.127 "cd /home/smartiva/office/projects/8002-talco-dintec && rm -rf web/node_modules web/dist && tar -xzf /tmp/talco-web-release.tar.gz && docker compose -f docker-compose.vps.yml up -d --build --wait talco-v1-web && rm -f /tmp/talco-web-release.tar.gz"

Post-deployment check:

    ssh smartiva@100.73.142.127 "cd /home/smartiva/office/projects/8002-talco-dintec && docker compose -f docker-compose.vps.yml ps && docker compose -f docker-compose.vps.yml exec -T talco-v1-api alembic current && curl -fsS https://talco.smartiva.tech/health"

All three containers must be healthy and the portal must return HTTP 200.

## 9. Secrets and settings

Production secrets are in:

    /home/smartiva/office/projects/8002-talco-dintec/.env

Never replace this file with .env.example.

Main variables:

- TALCO_DB_PASSWORD
- PUBLIC_URL
- VAPID_PUBLIC_KEY
- VAPID_PRIVATE_KEY
- VAPID_SUBJECT

SMTP and WhatsApp credentials are stored through Admin Settings in PostgreSQL. Secret values are write-only through the API.

## 10. Main API groups

- /api/auth — login, invitations, reset, verification and keep-alive.
- /api/dashboard — admin/member dashboard.
- /api/tanneries — Tannery Master.
- /api/pumps — Pump Master.
- /api/accounts — Ledger Master/opening balances.
- /api/users — user account access.
- /api/imports — Excel/XML review/post/corrections.
- /api/mappings — alias binding.
- /api/portal — ledger/invoice/receipt/PDF, plus /invoices/{id}/preview which serves the same invoice as HTML for phones.
- /api/circulars — notice board/attachments/read/pagination.
- /api/notifications — notification state/subscriptions/logs.
- /api/settings — profile/company/logo/SMTP/WhatsApp.
- /api/reports — admin outstanding summary (JSON and CSV).
- /api/notifications/delivery-log — filtered, paginated delivery attempts (admin).
- /api/notifications/deliveries/{type}/{id} — recipients, per-channel status and read state (admin).
- /api/settings/channels — circular delivery switches (admin).
- /health — application/database health.

## 11. Recommended next work

### Remaining Phase 1 gaps

Not yet built, in the order they were agreed with the client:

1. Month-wise collection, head-wise revenue and member-wise ledger reports.
   The outstanding summary is done.
2. Statement Excel export, member-selectable date range, and the head-wise
   statement variant. Keep the dashboard combined - do not add per-head tiles.
4. English/Tamil i18n. No scaffolding exists and every screen is hardcoded
   English. UI labels in both; bill and statement content stays English.
5. Batch versioning keyed on (head, period), and flagging invoices whose
   values changed after dispatch with a "changed since sent - resend?" action.
   Bill dispatch now records a notification per invoice, so that flag has
   something to compare against.
6. A printable credential sheet. Creating an account shows the login and password once; there is no print or batch export yet.

Hosting is still talco.smartiva.tech. The client asked for
portal.talcodintec.com, which needs a CNAME from whoever runs that domain
plus TLS for the subdomain.

### Production UAT

Use real accounts to verify:

- Invitation/setup/reset delivery.
- Username/email/phone login.
- Email and WhatsApp verification.
- Push delivery.
- Circular attachment download and read state.
- Mobile PWA session restore.
- Real monthly Sales/Receipt import.
- Invoice and receipt printing on Android and desktop.

### Optional later modules

- Outstanding payment reminders.
- Complaint/request module.
- Admin ticket management.
- Detailed audit overview.
- Reconciliation report.
- Advanced import history/export.

## 12. Minimum completion checklist

Backend change:

    docker compose build api
    docker compose run --rm api pytest -q

Frontend change:

    cd web
    npm run build

Before commit:

    git diff --check
    git status --short

After deployment:

1. Containers healthy.
2. Migration at head.
3. Health reports database reachable.
4. Login works.
5. Changed desktop/mobile screen works.
6. Existing ledger/import/access behavior is unchanged.

## 13. Files and artifacts

- source-data/ contains development import samples.
- .codex-remote-attachments/ contains supplied reference attachments.
- output/ is untracked and must stay out of Git.
- tmp/ is only for temporary verification and should be cleaned.
- Archive/ contains superseded project documentation.

## 14. Start of next session

1. Read this file.
2. Check git status, branch and latest commit.
3. Run the relevant baseline tests.
4. Implement one bounded change.
5. Verify, commit and push locally.
6. Deploy through the source-only archive workflow.
7. Verify production health and manually test the changed flow.
