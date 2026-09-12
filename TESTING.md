# Talco-Dintec Portal — Test Guide

Site: `https://talco.smartiva.tech`

VM-la test panna: `http://127.0.0.1:8002`

## Deployment smoke test

1. Login page open aaganum.
2. Existing admin login use panni login aaganum.
3. Left menu-la **Tannery Master**, **Pump Master**, **Ledger Master** varanum.
4. Tannery Master-la list open aagi add/edit work aaganum; new tannery serial number
   automatic-a varanum.
5. Pump Master add/edit work aaganum; Tannery form-la pump select panna mudiyanum.
6. Ledger Master-la opening balance, date, Dr/Cr edit panni save panna mudiyanum.
7. User access-la ore login-ku multiple ledger accounts assign panna mudiyanum.
8. Account Statement-la internal `legacy-...` ID theriyakoodadhu. Bill/receipt number
   illa-na **Not provided** varanum; balance **Amount due** illa
   **Advance / credit available** nu meaningful-a varanum.

Test mudinjadhum `VPS smoke test pass` illa problem-oda screen/name anuppunga.


## Invoice correction and printing

1. Existing invoice-oda amount maathi corrected Tally XML upload pannunga.
2. Invoice automatic-a overwrite aagakoodadhu; **Correction detected** nu old/new values varanum.
3. Reason empty-a vachu **Replace** panna reject aaganum.
4. Reason enter panni **Replace with corrected invoice** press pannunga.
5. Ledger balance corrected total-ku update aaganum; invoice view-la correction count varanum.
6. **Keep existing** use pannina old invoice amount maarakoodadhu.
7. Account Ledgers → **Print ledger** open panni A4 preview readable-a irukkanum.
8. All bills → **View / Print** → **Print invoice** open panni account, tannery, bill number,
   date, charge, CGST, SGST and total varanum.

Test mudinjadhum: VPS invoice correction and print test pass
## 2026-09-11 - Complete Tally XML import phase

- Full Tally ENVELOPE/VOUCHER XML and legacy DBCFIXED exports are supported.
- UTF-16 exports and invalid Tally control references such as numeric control 4 are cleaned during parsing.
- Mixed Sales and Receipt vouchers can be uploaded in one monthly file.
- Stable Tally GUID and ALTERID are retained; re-exports use GUID first, then voucher number and FY.
- Effluent Treatment Charges is exactly mapped to TREATMENT; manual charge-head override remains available.
- New Ref and Agst Ref bill allocations are stored and receipts are linked to matching invoices.
- Changed or cancelled existing Sales/Receipt vouchers wait for admin review with a required reason and audit log.
- Cancelled vouchers are excluded from account ledger totals and lists.
- Import review shows voucher number/type, GUID, charge ledger, bill reference, duplicate and cancelled counts.
- Validation: supplied Transactions.xml parsed as 16 Sales and 1 Receipt; backend Docker tests 58 passed; frontend production build passed; local containers healthy.

## 2026-09-11 - Excel-first transaction import

- Import screen accepts .xlsx, .xlsm, and .xml; Excel is presented as the recommended format.
- Sales workbook supports the current three-sheet Tally ledger report and a flat template-style layout.
- Charge head is detected from sheet title or Charge Head column.
- Missing CGST/SGST is calculated from the configured charge rate using Tally-matching whole-rupee half-up rounding.
- Missing invoice total is calculated from taxable amount plus CGST and SGST.
- Missing voucher number and receipt bill reference are warnings, not batch-blocking errors.
- Receipts without an against-invoice reference post as unallocated receipts.
- Rows with essential invalid data remain in error, while other matched rows can still be posted.
- Real file review validation: Sales - Aug 2026.xlsx 61/61 matched, base 4523415, gross 4760477; Receipt Register.xlsx 53/53 matched, total 5766381.
- Automated validation: parser tests 8 passed, full Docker backend suite 60 passed, frontend production build passed.

## 2026-09-11 - Settings, profiles, branding, and light theme

- Every login has Settings with display name, email, phone, and current-password verified password change.
- Admin Settings includes company profile, registered address, GSTIN, contact details, website, and logo upload.
- Logos accept PNG, JPEG, or WebP up to 2 MB and persist in PostgreSQL across container rebuilds.
- SMTP configuration supports host, port, username, write-only password, from identity, STARTTLS/SSL/none, and enable control.
- SMTP passwords are never returned by the API or written into audit records.
- Company, logo, SMTP, profile, and password changes create audit entries.
- Sidebar shows configured short name and logo after reload.
- Application theme uses warm light surfaces, traditional deep green navigation, restrained gold actions, and higher-contrast form controls.
- Validation: backend Docker tests 62 passed; frontend production build passed; local containers healthy.

## 2026-09-11 - Smartiva ERP UI baseline

- Applied the local smartiva-erp-ui skill as the design reference without introducing Smartiva product branding.
- Shared visual tokens now use teal #0CA678, neutral light canvas, white surfaces, subtle gray borders, semantic danger/warning colors, and 8 px radius.
- Desktop navigation is a compact 250 px white ERP sidebar with teal active state.
- Tables use compact rows, clear headers, zebra scanning, tabular numerals, and safe overflow behavior.
- Forms use consistent white controls, visible teal keyboard focus, and compact spacing.
- Mobile navigation scrolls horizontally without clipping destinations.
- Existing TALCO branding, routes, business rules, and data remain unchanged.
- Validation: frontend TypeScript and Vite production build passed; local Docker services healthy.

## 2026-09-11 - Light list row contrast fix

- Legacy opacity row utilities are overridden at the shared table layer.
- List tables now use white rows, pale teal zebra rows, and a light teal hover state.
- Opening rows retain a semantic teal-tinted background.
- Verified with the frontend TypeScript and Vite production build.

## 2026-09-12 - Circulars and Notice Board

1. Admin / TALCO staff login panni left menu-la **Circulars** open pannunga.
2. Title, category, priority, complete message enter panni **All portal users** select செய்து publish pannunga.
3. PDF/image/Word/Excel attachment optional-a upload panna mudiyanum; 8 MB-ku mela reject aaganum.
4. Member login-la **Notice Board** open pannina published circular top-la varanum.
5. Circular open pannumbodhu full message readable-a irukkanum; attachment irundha download aaganum.
6. Unread green dot circular open pannadhum read-a maaranum; admin history-la read count update aaganum.
7. **Selected users** choose panni publish pannina selected login-ku mattum varanum; vera member-ku varakoodadhu.
8. **Valid until** mudinja circular member notice board-la varakoodadhu.
9. **Save draft** member-kku kaattakoodadhu. Admin history-la Draft badge-oda mattum irukkanum.
10. Admin circular delete panna notice board-layum remove aaganum; TALCO staff delete panna mudiyakoodadhu.

Test mudinjadhum: **VPS Circulars and Notice Board test pass**

## 2026-09-12 - Dashboards, mobile PWA and notifications

1. Admin login pannina first **Dashboard** open aaganum; tannery count, portal user count, outstanding, bills, collections and recent imports varanum.
2. Member login pannina own dashboard mattum varanum; assigned ledger accounts and total outstanding mattum theriyanum.
3. Phone-la Tannery, Pump, Ledger, Users, Imports, Mapping and delivery-log tables horizontal scroll aagakoodadhu; ovvoru row-um label-oda card mathiri full width-la varanum.
4. Chrome mobile menu-la **Install app / Add to Home screen** use panni TALCO app install panna mudiyanum; standalone-a open aaganum.
5. Settings → **Mobile push notifications** → Enable press panni browser permission Allow pannunga.
6. Admin or staff new circular publish pannina notification bell count update aaganum; mobile push enabled device-ku notification varanum.
7. Notification click pannina TALCO Notice Board open aaganum.
8. Settings → **Send verification email** press pannunga. Inbox link click pannina email verified message varanum.
9. Email change pannina verification status thirumba Pending aaganum.
10. Admin Settings-la **Notification delivery log** open panni email/push sent, failed, skipped status and time பார்க்க முடியணும்.
11. SMTP disabled/failed na user-kku meaningful message varanum; admin log-la exact failure reason varanum.
12. Android portrait, Android landscape, desktop 1366px-la navigation, forms, dialogs and cards clipping illama work aaganum.

Test mudinjadhum: **VPS dashboard, mobile PWA and notifications test pass**

## 2026-09-12 - Ledger closing, formal print and mobile menu

1. Admin → **Ledger Master** open pannunga. List-la Opening balance-ku badhila current **Closing balance** varanum.
2. Invoice/receipt post aana udane Ledger Master closing recalculate aaganum; opening date-ku munnaadi entries double count aagakoodadhu.
3. Amount receivable / Dr balance red-la varanum; advance / Cr balance green-la varanum.
4. Member Dashboard-la total closing and ovvoru ledger account closing front-la Dr/Cr-oda varanum.
5. Account Ledgers statement-la running balance font dark/readable-a irukkanum; Dr red, Cr green-a irukkanum.
6. **Print ledger** click panni print preview open pannunga. App sidebar/cards print aagakoodadhu.
7. Print-la TALCO letterhead, period, account, tannery, Date, Particulars, Vch Type, Vch No., Debit, Credit, totals, Closing Balance and Authorised Signatory area varanum.
8. Mobile portrait-la top horizontal menu varakoodadhu. **☰ hamburger** press pannina side drawer open aaganum; menu select pannina drawer close aaganum.
9. Mobile header-la logo/name and notification bell visible-a irukkanum.
10. Admin Dashboard-la Tannery, Pump, Ledger, Import, Circular shortcut cards; member Dashboard-la My Ledgers, Notice Board, Settings shortcut cards work aaganum.

Test mudinjadhum: **VPS ledger closing, formal print and hamburger menu test pass**

## 2026-09-12 - SMTP delivery test

1. Admin login panni **Settings → Email / SMTP** open pannunga.
2. SMTP host, port, username, password, from email and security mode correct-a save pannunga.
3. **Test SMTP delivery** section-la receive panna mudiyura real email address enter pannunga.
4. **Send test email** press pannina success message varanum; inbox/spam-la TALCO SMTP test mail varanum.
5. Failure vandha same page-la meaningful reason varanum; **Notification delivery log**-la failed status and reason varanum.
6. Test mail successful-a vandha piragu SMTP enable செய்து settings save pannunga.

Current VPS network check: configured port 467 timeout; ports 465 and 587 reachable. Security mode-ku match aagura correct port-ai use pannavum.

Test mudinjadhum: **VPS SMTP test pass**
## 2026-09-12 - Email invitation, password setup and persistent login

1. Admin → **Users & Account Access**-la real member email, role, ledger access select panni **Create Invitation** press pannunga.
2. Admin screen/API-la setup token kaattakoodadhu; **Invitation email sent** message varanum.
3. Member inbox-la TALCO invitation mail varanum. Link 48 hours valid; link click pannina TALCO logo, readonly login email, New password, Confirm password fields varanum.
4. Password mismatch-na save aagakoodadhu. Valid password set pannina direct-a member dashboard open aaganum.
5. Same invitation link second time open pannina expired/used message varanum.
6. Pending user-ku admin user list-la **Resend invitation** use pannina old link invalid aagi new mail varanum.
7. Login page-la **Forgot password?** open panni registered email submit pannina reset email varanum. Unknown email-kum same neutral response varanum.
8. Reset link 1 hour valid. Password reset pannina old logged-in sessions revoke aagi, current device new session-oda direct login aaganum.
9. Browser/PWA close-open, phone restart pannalum login continue aaganum. Manual logout press pannina mattum session close aaganum.
10. Invitation/reset delivery failure-na admin **Notification delivery log**-la exact SMTP reason varanum.

Test mudinjadhum: **VPS email invitation and persistent login test pass**