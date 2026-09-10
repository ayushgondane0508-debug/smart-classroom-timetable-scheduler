import asyncio
import os

import resend

DAY_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def email_configured():
    return bool((os.environ.get("RESEND_API_KEY") or "").strip())


def schedule_html(teacher, timetable, entries, portal_url):
    ordered = sorted(entries, key=lambda e: (DAY_ORDER.index(e["day"]) if e["day"] in DAY_ORDER else 99, e["period"]))
    rows = ""
    for day in dict.fromkeys(e["day"] for e in ordered):
        day_entries = [e for e in ordered if e["day"] == day]
        cells = "".join(f'<tr><td style="padding:6px 10px;color:#64748b;font-size:12px">P{e["period"]}</td><td style="padding:6px 10px;font-size:13px"><b>{e.get("subject_code") or e["subject_name"]}</b> · {e["division_name"]}</td><td style="padding:6px 10px;color:#2563eb;font-size:12px">{e["room_name"]}</td></tr>' for e in day_entries)
        rows += f'<tr><td colspan="3" style="padding:14px 10px 4px;font-weight:700;font-size:13px;color:#0f172a;border-top:1px solid #e2e8f0">{day}</td></tr>{cells}'
    return f'''<table width="100%" cellpadding="0" cellspacing="0" style="font-family:Arial,sans-serif;background:#f4f7fb;padding:24px"><tr><td align="center"><table width="560" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:14px;overflow:hidden"><tr><td style="background:#0b1324;padding:22px 26px;color:#fff"><div style="font-size:11px;letter-spacing:.16em;text-transform:uppercase;color:#14b8a6;font-weight:700">Smart Classroom</div><div style="font-size:22px;font-weight:700;margin-top:6px">A new timetable has been published</div></td></tr><tr><td style="padding:22px 26px;color:#334155;font-size:14px;line-height:1.6">Hello {teacher["name"]},<br/>The admin has published <b>{timetable.get("name", "a new timetable")}</b>. You have <b>{len(entries)} sessions</b> this week. Your updated schedule is below.<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px;border-collapse:collapse">{rows}</table><div style="margin-top:22px"><a href="{portal_url}" style="background:#2563eb;color:#fff;text-decoration:none;padding:12px 18px;border-radius:10px;font-weight:700;font-size:13px;display:inline-block">Open my schedule</a></div></td></tr><tr><td style="padding:14px 26px;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0">Sent automatically by Smart Classroom &amp; Timetable Scheduler.</td></tr></table></td></tr></table>'''


async def send_email(to, subject, html):
    if not email_configured():
        return {"status": "skipped", "error": "RESEND_API_KEY not configured — alert logged only"}
    resend.api_key = os.environ["RESEND_API_KEY"].strip()
    try:
        result = await asyncio.to_thread(resend.Emails.send, {"from": os.environ["SENDER_EMAIL"], "to": [to], "subject": subject, "html": html})
        return {"status": "sent", "provider_id": result.get("id") if isinstance(result, dict) else str(result)}
    except Exception as exc:
        return {"status": "failed", "error": str(exc)[:300]}
