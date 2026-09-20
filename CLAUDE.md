# TALCO-DINTEC Member Portal — Development Handoff

Last updated: 20 September 2026
Stable Git commit: dd81a8a
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
- api/app/services/invoice_pdf.py — Tally-style invoice and receipt PDFs.
- api/app/services/scope.py — shared member/account access scoping.
- api/app/services/notifications.py — email and push delivery.
- api/app/services/whatsapp.py — FII Tech WhatsApp API.
- api/alembic/versions/ — migrations.
- api/tests/ — regression tests.

Frontend: React, TypeScript, Vite, Tailwind utilities, shared CSS tokens and PWA service worker.

- web/src/App.tsx — authenticated shell, navigation and session restore.
- web/src/DashboardPage.tsx — admin/member dashboards.
- web/src/PortalPage.tsx — ledger, invoices, receipts and PDF preview.
- web/src/ImportsPage.tsx — imports and correction review.
- web/src/CircularsPage.tsx — circular and notice board.
- web/src/SettingsPage.tsx — profile/company/SMTP/WhatsApp settings.
- web/src/styles.css — DINTEC UI system and legacy-colour normalization.
- web/src/theme.ts — active theme tokens.
- web/public/sw.js — PWA cache; current key talco-shell-v7.

## 3. Completed functionality

Authentication and users:

- Admin bootstrap, invitations and email-delivered setup links.
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
- Invoice bank fields currently show a dash because bank details are not stored yet. Never hardcode values from a screenshot.

Circulars/notifications:

- Draft/publish, all or selected recipients, expiry and deletion.
- PDF/image/Word/Excel attachments up to 8 MB and secured download.
- Read/unread, filters and pagination.
- Notification bell, notification pagination/read state.
- SMTP test and delivery logs.
- Web push subscriptions.
- WhatsApp API settings, test and phone verification.

UI/PWA:

- Separate admin and member dashboards.
- Last Sync on from latest posted import.
- DINTEC navy/dark-sidebar/light-canvas theme.
- Old hardcoded teal/cyan/blue actions mapped to active theme tokens.
- Mobile drawer, bottom navigation and card-style tables.
- Installable PWA and persistent session.
- Theme Designer hidden; Help page removed.
- Smartiva.in/FII Tech.in footer remains.

## 4. Production baseline

Containers:

- talco-v1-postgres — internal database.
- talco-v1-api — internal API.
- talco-v1-web — Nginx gateway.
- Only 127.0.0.1:8002 is published.

Current migration: 0016_user_username (head).

Latest verification:

- Backend: 83 tests passed.
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

Current expected result: 83 passed.

Frontend verification:

    cd web
    npm install
    npm run build

Migration verification:

    docker compose run --rm api alembic upgrade head

The next migration must follow 0016_user_username. Test every migration against PostgreSQL.

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
- /api/portal — ledger/invoice/receipt/PDF.
- /api/circulars — notice board/attachments/read/pagination.
- /api/notifications — notification state/subscriptions/logs.
- /api/settings — profile/company/logo/SMTP/WhatsApp.
- /health — application/database health.

## 11. Recommended next work

### Company bank details

The invoice layout is ready but bank values are blank. Recommended:

1. Add bank_name, bank_account_number, bank_branch and bank_ifsc to CompanySetting.
2. Add migration 0017_company_bank_details.
3. Add Admin Settings fields and API serialization.
4. Use these fields in invoice_pdf.py.
5. Test and visually render A4 output.

Never copy the sample screenshot's bank details.

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
