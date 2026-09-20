from sqlalchemy import select
from app.models import AuditLog, CompanySetting
from app.models.auth import User
from app.security import hash_password, verify_password
from test_tannery_crud import master_api

def test_admin_company_smtp_and_logo_are_audited(master_api):
    client, headers, factory = master_api
    company={"company_name":"TALCO Test Ltd","short_name":"TALCO","address":"Road","city":"Dindigul","state":"Tamil Nadu","postal_code":"624002","gstin":"33TEST","phone":"123","email":"office@example.test","website":"https://example.test"}
    assert client.put("/api/settings/company",headers=headers["talco_staff"],json=company).status_code==403
    assert client.put("/api/settings/company",headers=headers["talco_admin"],json=company).status_code==200
    smtp={"smtp_host":"smtp.example.test","smtp_port":587,"smtp_username":"mailer","smtp_password":"secret-value","smtp_from_email":"office@example.test","smtp_from_name":"TALCO","smtp_security":"starttls","smtp_enabled":True}
    assert client.put("/api/settings/smtp",headers=headers["talco_admin"],json=smtp).status_code==200
    settings=client.get("/api/settings",headers=headers["talco_admin"]).json()
    assert settings["smtp"]["password_configured"] is True
    assert "smtp_password" not in settings["smtp"]
    assert client.post("/api/settings/logo",headers=headers["talco_admin"],files={"file":("logo.png",b"fake-png","image/png")}).status_code==200
    assert client.get("/api/settings/logo").content==b"fake-png"
    with factory() as session:
        assert session.get(CompanySetting,1).smtp_password=="secret-value"
        assert session.scalar(select(AuditLog).where(AuditLog.action=="logo_update"))

def test_user_can_update_own_profile_and_password(master_api):
    client,headers,factory=master_api
    with factory() as session:
        user=session.scalar(select(User).where(User.email=="member@test.local"));user.password_hash=hash_password("old-password");session.commit()
    changed=client.put("/api/settings/profile",headers=headers["member"],json={"display_name":"Member One","email":"member.one@test.local","phone":"99999"})
    assert changed.status_code==200
    assert client.put("/api/settings/password",headers=headers["member"],json={"current_password":"wrong-value","new_password":"new-password"}).status_code==422
    assert client.put("/api/settings/password",headers=headers["member"],json={"current_password":"old-password","new_password":"new-password"}).status_code==200
    with factory() as session:
        user=session.scalar(select(User).where(User.email=="member.one@test.local"));assert verify_password("new-password",user.password_hash)

def test_admin_can_send_logged_smtp_test_while_delivery_disabled(master_api, monkeypatch):
    client, headers, factory = master_api
    smtp = {"smtp_host":"smtp.example.test","smtp_port":587,"smtp_username":"mailer",
        "smtp_password":"secret-value","smtp_from_email":"office@example.test",
        "smtp_from_name":"TALCO","smtp_security":"starttls","smtp_enabled":False}
    assert client.put("/api/settings/smtp", headers=headers["talco_admin"], json=smtp).status_code == 200
    sent = []
    class FakeSmtp:
        def __init__(self, *args, **kwargs): pass
        def starttls(self, **kwargs): pass
        def login(self, username, password): assert username == "mailer"
        def send_message(self, message): sent.append(message)
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr("app.services.notifications.smtplib.SMTP", FakeSmtp)
    response = client.post("/api/settings/smtp/test", headers=headers["talco_admin"],
                           json={"recipient":"real@example.test"})
    assert response.status_code == 200, response.text
    assert sent[0]["To"] == "real@example.test"
    assert client.post("/api/settings/smtp/test", headers=headers["talco_staff"],
                       json={"recipient":"real@example.test"}).status_code == 403
    with factory() as session:
        from app.models import DeliveryLog
        delivery = session.scalar(select(DeliveryLog).where(DeliveryLog.channel == "email"))
        assert delivery.status == "sent"
        assert delivery.destination == "real@example.test"


def test_admin_can_publish_theme_for_all_users(master_api):
    client, headers, session_factory = master_api
    theme = {
        "theme_name": "High Visibility", "background_color": "#f4f4f4", "surface_color": "#ffffff",
        "font_color": "#111111", "muted_color": "#444444", "primary_color": "#005f46",
        "primary_text_color": "#ffffff", "edit_color": "#8a4b00", "view_color": "#004b76",
        "print_color": "#005f46", "danger_color": "#b42318", "border_color": "#b8c2bd",
        "header_color": "#102f4f", "sidebar_color": "#0e1830", "sidebar_text_color": "#d8e4f4",
        "active_nav_color": "#246bfe", "accent_color": "#234396", "success_color": "#00a878",
        "warning_color": "#f4b400"
    }
    assert client.put("/api/settings/theme", headers=headers["talco_staff"], json=theme).status_code == 403
    response = client.put("/api/settings/theme", headers=headers["talco_admin"], json=theme)
    assert response.status_code == 200
    assert client.get("/api/settings/public").json()["theme"] == theme
    with session_factory() as session:
        assert session.query(AuditLog).filter_by(entity_type="theme_setting", action="update").count() == 1


def test_admin_whatsapp_settings_and_member_phone_verification(master_api, monkeypatch):
    client, headers, factory = master_api
    payload = {"whatsapp_base_url":"https://wapi.example.test", "whatsapp_api_key":"secret-api-key",
               "whatsapp_device_id":31, "whatsapp_enabled":True}
    assert client.put("/api/settings/whatsapp", headers=headers["talco_staff"], json=payload).status_code == 403
    saved = client.put("/api/settings/whatsapp", headers=headers["talco_admin"], json=payload)
    assert saved.status_code == 200, saved.text
    settings = client.get("/api/settings", headers=headers["talco_admin"]).json()["whatsapp"]
    assert settings["api_key_configured"] is True
    assert "whatsapp_api_key" not in settings
    with factory() as session:
        row = session.get(CompanySetting, 1)
        assert row.whatsapp_api_key == "secret-api-key"
        member = session.scalar(select(User).where(User.email == "member@test.local"))
        member.phone = "9876543210"
        session.commit()
    monkeypatch.setattr("app.routers.auth.secrets.randbelow", lambda _: 123456)
    monkeypatch.setattr("app.routers.auth.send_whatsapp", lambda *args, **kwargs: True)
    sent = client.post("/api/auth/phone-verification/request", headers=headers["member"])
    assert sent.status_code == 200, sent.text
    confirmed = client.post("/api/auth/phone-verification/confirm", headers=headers["member"], json={"code":"123456"})
    assert confirmed.status_code == 200, confirmed.text
    assert client.get("/api/auth/me", headers=headers["member"]).json()["phone_verified"] is True


def test_company_bank_details_round_trip_and_stay_off_public_endpoint(master_api):
    client, headers, factory = master_api
    company={"company_name":"TALCO Test Ltd","short_name":"TALCO","address":"Road","city":"Dindigul",
        "state":"Tamil Nadu","postal_code":"624002","gstin":"33TEST","phone":"123",
        "email":"office@example.test","website":"https://example.test",
        "bank_name":"Test Bank","bank_account_number":"000111222333","bank_branch":"Dindigul Main",
        "bank_ifsc":"TEST0001234"}
    saved=client.put("/api/settings/company",headers=headers["talco_admin"],json=company)
    assert saved.status_code==200
    assert saved.json()["bank_account_number"]=="000111222333"
    settings=client.get("/api/settings",headers=headers["talco_admin"]).json()
    assert settings["company"]["bank_name"]=="Test Bank"
    assert settings["company"]["bank_ifsc"]=="TEST0001234"
    public=client.get("/api/settings/public").json()
    for key in ("bank_name","bank_account_number","bank_branch","bank_ifsc"):
        assert key not in public
    with factory() as session:
        assert session.get(CompanySetting,1).bank_branch=="Dindigul Main"


def test_invoice_bank_block_uses_stored_values_and_falls_back_to_dash():
    from app.services.invoice_pdf import _or_dash
    assert _or_dash("Test Bank")=="Test Bank"
    assert _or_dash("  ")=="\u2014"
    assert _or_dash(None)=="\u2014"
    assert _or_dash("A & B Bank")=="A &amp; B Bank"
