"""Generate a ready-to-copy application email for a listing."""
from __future__ import annotations

from datetime import date


def _fmt_move_in(iso: str | None, lang: str) -> str:
    """'2026-08-01' -> 'ab dem 01.08.2026' / 'from 01.08.2026'."""
    if not iso:
        return "ab sofort" if lang == "de" else "as soon as possible"
    try:
        d = date.fromisoformat(iso)
        ds = d.strftime("%d.%m.%Y")
    except ValueError:
        ds = iso
    return (f"ab dem {ds}" if lang == "de" else f"from {ds}")


def _contact_line(app: dict, lang: str) -> str:
    parts = []
    if app.get("contact_phone"):
        parts.append(("Telefon: " if lang == "de" else "Phone: ") + app["contact_phone"])
    if app.get("contact_email"):
        parts.append("E-Mail: " + app["contact_email"])
    return " · ".join(parts)


def build_draft(listing: dict, cfg) -> dict:
    """Return {subject, body} for one listing."""
    app = cfg.applicant
    lang = app.get("language", "de")
    move_in = _fmt_move_in(cfg.move_in_from, lang)

    title = listing.get("title") or ""
    city = listing.get("city") or ""
    district = listing.get("district") or ""
    where = city + (f"-{district}" if district and district != city else "")
    rooms = listing.get("rooms")
    rooms_txt = f"{int(rooms)}-Zimmer-" if rooms else ""

    contact = _contact_line(app, lang)
    household = app.get("household", "")
    household_cap = household[:1].upper() + household[1:] if household else ""

    if lang == "en":
        subject = f"Application for your apartment: {title}"
        body = f"""Dear Sir or Madam,

I saw your listing "{title}" in {where or city} with great interest and would like to apply for the apartment.

{household_cap} We are looking for a new home {move_in} in {city}. {app.get('occupation','')} {app.get('pets','')}

{app.get('extras','')}

We would be very happy about the opportunity to view the apartment. You can reach us at {contact or app.get('contact_email','')}.

Kind regards
{app.get('signature','')}"""
    else:
        subject = f"Bewerbung für Ihre {rooms_txt}Wohnung in {city}: {title}"
        body = f"""Sehr geehrte Damen und Herren,

mit großem Interesse habe ich Ihre Anzeige „{title}" in {where or city} gesehen und möchte mich hiermit um die Wohnung bewerben.

{household_cap} suchen {move_in} ein neues Zuhause in {city}. {app.get('occupation','')} {app.get('pets','')}

{app.get('extras','')}

Über die Möglichkeit einer Besichtigung würden wir uns sehr freuen. Sie erreichen uns unter {contact or app.get('contact_email','')}.

Mit freundlichen Grüßen
{app.get('signature','')}"""

    # tidy up double spaces / blank runs
    body = "\n".join(line.rstrip() for line in body.splitlines())
    while "  " in body:
        body = body.replace("  ", " ")
    return {"subject": subject, "body": body}
