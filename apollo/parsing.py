"""Stateless parsers for Apollo page text (no Selenium, no globals)."""
import re
import logging
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


def convert_count(c):
    """Convert count string to integer (handles K, M suffixes)"""
    if not c or not isinstance(c, str):
        return 0
    c = c.upper().replace(",", "").strip()
    if not c:
        return 0
    try:
        return int(float(c.replace("K", "")) * 1000) if "K" in c else int(c)
    except:
        return 0


def convert_date(dstr):
    """Convert date string to datetime object"""
    if not dstr or not isinstance(dstr, str):
        return datetime.now()
    # Apollo tooltip format is "Jul 8, 2026, 11:34 AM" (comma before the time).
    for fmt in ("%b %d, %Y, %I:%M %p", "%b %d, %Y %I:%M %p", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dstr.strip(), fmt)
        except (ValueError, TypeError):
            continue
    return datetime.now()


def get_past_renewal_credit_periods(renewal_date, months=6):
    renewal_dates = []

    # Generate past (months + 1) renewal dates
    for i in range(months, -1, -1):  # e.g., 2 → 1 → 0
        past_date = renewal_date - relativedelta(months=i)
        last_day = (past_date + relativedelta(day=31)).day
        adjusted_day = min(renewal_date.day, last_day)
        past_date = past_date.replace(day=adjusted_day)
        renewal_dates.append(past_date)

    # Create (start, end) periods
    periods = []
    for i in range(months):
        start = renewal_dates[i] + timedelta(days=1)
        end = renewal_dates[i + 1] 
        end = end.replace(hour=start.hour, minute=start.minute)  # preserve time
        periods.append((start, end))

    return periods


CREDIT_USAGE_PATTERNS = (
    ('A:credits/mo', r'(\d[\d,]*)\s+credits\s+of\s+(\d[\d,]*)\s+credits\s*/\s*mo'),
    ('B:emails/mo', r'Email\s+credits\s+usage\s*(\d[\d,]*)\s+of\s+(\d[\d,]*)\s+emails?\s*/\s*mo'),
    ('C:donut', r'(\d[\d,]*)\s+of\s+(\d[\d,]*)\s+credits\s+used'),
)


RENEWAL_PATTERNS = (
    r'Estimated Credit Renewal on:\s*([A-Za-z]{3} \d{1,2}, \d{4},? \d{1,2}:\d{2} [AP]M)',
    r'Credits will renew on\s*([A-Za-z]{3} \d{1,2}, \d{4},? \d{1,2}:\d{2} [AP]M)',
)


def extract_credit_usage(body_text):
    """Return (used_credits, total_credits) from any known layout, else (0, 0).

    Pass the Selenium body text (not soup text) - see note above."""
    for label, pat in CREDIT_USAGE_PATTERNS:
        m = re.search(pat, body_text or '', re.IGNORECASE)
        if m:
            used = int(m.group(1).replace(',', ''))
            total = int(m.group(2).replace(',', ''))
            print(f'[CREDITS DATA] Layout {label}: used={used} total={total}')
            return used, total
    print('[CREDITS DATA] No known credit-usage layout matched')
    return 0, 0


def extract_renewal_date(body_text, soup_text='', current_url=''):
    """Return the next credit renewal datetime, or None.

    Tries every known layout phrasing against both the body text and the soup
    text, then falls back to deriving it from the URL: Apollo redirects
    /settings/credits/current to ?minDate=<cycle start>&datePreset=current_billing_cycle,
    and the cycle start is the previous renewal, so renewal = minDate + 1 month.
    (Verified: minDate=2026-06-27 -> "Credits will renew on Jul 27, 2026, 9:14 AM".)"""
    for text in (body_text, soup_text):
        if not text:
            continue
        for pat in RENEWAL_PATTERNS:
            m = re.search(pat, text, re.IGNORECASE)
            if not m:
                continue
            raw = m.group(1)
            for fmt in ('%b %d, %Y, %I:%M %p', '%b %d, %Y %I:%M %p'):
                try:
                    return datetime.strptime(raw, fmt)
                except ValueError:
                    continue

    # Fallback: derive from the billing-cycle start in the URL.
    m = re.search(r'minDate=(\d{4}-\d{2}-\d{2})', current_url or '')
    if m:
        try:
            derived = datetime.strptime(m.group(1), '%Y-%m-%d') + relativedelta(months=1)
            print(f'[CREDITS DATA] Renewal text not found - derived {derived:%Y-%m-%d} '
                  f'from URL minDate={m.group(1)}')
            logging.info(f'Renewal date derived from URL minDate={m.group(1)} -> {derived:%Y-%m-%d}')
            return derived
        except ValueError:
            pass
    return None
