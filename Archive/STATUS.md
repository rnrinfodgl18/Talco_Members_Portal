# Talco-Dintec portal — status

Updated: 2026-09-12

The earlier VPS sample application has been replaced by the current `webApp-v1`
application. It includes Tannery Master, Pump Master, automatic tannery serial
numbers, Ledger Master with opening balances, multi-ledger access under one login,
Tally invoice/receipt imports, customer account statements, explicit invoice correction approval with revision/audit history, printable ledger/invoice views, and Circulars with a member Notice Board, targeted delivery, attachments, expiry, read receipts, separate admin/member dashboards, installable PWA support, mobile card tables, email verification, and in-app/email/push notification delivery logs, calculated Ledger Master closings, Tally-style ledger print, mobile hamburger navigation, dashboard shortcuts, email-delivered invitations, branded password setup, secure forgot-password links, and persistent sessions.

VPS deployment:

- Portal: `127.0.0.1:8002`
- Public hostname: `talco.smartiva.tech`
- Compose file: `docker-compose.vps.yml`
- Public container: `talco-v1-web`
- Internal containers: `talco-v1-api`, `talco-v1-postgres`

The previous VPS project code and database dump are retained under
`/home/smartiva/backups/8002-talco-dintec/` for rollback.
