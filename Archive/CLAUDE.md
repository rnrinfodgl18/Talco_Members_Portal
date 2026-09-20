# Talco-Dintec portal — session rules

Read `STATUS.md` before changing the application and keep `TESTING.md` current.
The parent `/home/smartiva/office/OFFICE.md` rules also apply on the VPS.

Working rhythm:

1. Implement one requested change.
2. Run the relevant tests.
3. Deploy with `docker compose -f docker-compose.vps.yml up -d --build --wait`.
4. Check `http://127.0.0.1:8002/health` and the portal page.
5. Add concise Tanglish manual checks to `TESTING.md` and hand them to the Boss.

Non-negotiable application rules:

- Every financial query must use the shared account scope service.
- Tally imports are the source for invoices and receipts; imports must be idempotent.
- Administrative changes must be audited with their old and new values.
- Never print, copy into chat, or commit secrets. The VPS `.env` stays mode 600.
- Only the web gateway is published, at `127.0.0.1:8002`. API and PostgreSQL stay internal.
- Compose service names must remain globally unique on the shared `office` network.
