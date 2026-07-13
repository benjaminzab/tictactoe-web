#!/usr/bin/env python3
"""Check SEC EDGAR for new open-market insider buy/sell (Form 4) filings by
top executives at a fixed list of companies, and email any new ones found.

Run with no arguments for normal operation (reads/writes state.json, sends
email via Resend if RESEND_API_KEY is set and new qualifying trades are
found). Run with --dry-run to fetch and print findings without sending email
or updating state.json.
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import requests

USER_AGENT = "insider-trading-bot benjamin.472006@gmail.com"
STATE_PATH = Path(__file__).parent / "state.json"
NOTIFY_EMAIL = "benjamin.472006@gmail.com"
RESEND_API_URL = "https://api.resend.com/emails"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}

COMPANIES = {
    "Nvidia": {"cik": "1045810", "ticker": "NVDA"},
    "Amazon": {"cik": "1018724", "ticker": "AMZN"},
    "SolarEdge": {"cik": "1419612", "ticker": "SEDG"},
    "Digi Power X": {"cik": "1854368", "ticker": "DGXX"},
}

# Case-insensitive substrings matched against the Form 4 officerTitle field.
TITLE_KEYWORDS = [
    "chief executive officer", "ceo",
    "chief financial officer", "cfo",
    "chief technology officer", "cto",
    "vice president", "vp",
    "president",
    "chairman", "chair",
]

# Only open-market purchases/sales count as "bought or sold" for this bot.
TRANSACTION_CODES = {"P": "Purchase", "S": "Sale"}

session = requests.Session()
session.headers.update({"User-Agent": USER_AGENT})


def get(url):
    resp = session.get(url, timeout=30)
    resp.raise_for_status()
    return resp


def load_state():
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {}


def save_state(state):
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def title_matches(officer_title):
    title = (officer_title or "").lower()
    return any(kw in title for kw in TITLE_KEYWORDS)


def fetch_filing_list(cik):
    """Return recent Form 4 filings for an issuer CIK: [{accession, date, href}]."""
    url = (
        "https://www.sec.gov/cgi-bin/browse-edgar"
        f"?action=getcompany&CIK={cik}&type=4&dateb=&owner=include&count=100&output=atom"
    )
    root = ET.fromstring(get(url).content)
    filings = []
    for entry in root.findall("a:entry", ATOM_NS):
        content = entry.find("a:content", ATOM_NS)
        if content is None:
            continue
        accession = content.findtext("a:accession-number", default="", namespaces=ATOM_NS)
        date = content.findtext("a:filing-date", default="", namespaces=ATOM_NS)
        href = content.findtext("a:filing-href", default="", namespaces=ATOM_NS)
        if accession:
            filings.append({"accession": accession, "date": date, "href": href})
    return filings


def find_ownership_xml_url(cik, accession):
    """Locate the primary ownership XML document within a filing's folder."""
    accession_nodashes = accession.replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodashes}"
    index = get(f"{base}/index.json").json()
    items = index.get("directory", {}).get("item", [])
    for item in items:
        name = item.get("name", "")
        if name.endswith(".xml") and "index" not in name.lower():
            return f"{base}/{name}"
    return None


def parse_ownership_xml(xml_bytes):
    """Return (officer_title, issuer_name, owner_name, [transactions]) from
    a Form 4 ownership XML document. Each transaction dict has date, code,
    shares, price."""
    root = ET.fromstring(xml_bytes)

    issuer_name = root.findtext("issuer/issuerName", default="")
    owner_name = root.findtext("reportingOwner/reportingOwnerId/rptOwnerName", default="")
    officer_title = root.findtext(
        "reportingOwner/reportingOwnerRelationship/officerTitle", default=""
    )

    transactions = []
    for tx in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = tx.findtext("transactionCoding/transactionCode", default="")
        if code not in TRANSACTION_CODES:
            continue
        date = tx.findtext("transactionDate/value", default="")
        shares_raw = tx.findtext("transactionAmounts/transactionShares/value", default="")
        price_raw = tx.findtext("transactionAmounts/transactionPricePerShare/value", default="")
        try:
            shares = float(shares_raw)
            price = float(price_raw)
        except ValueError:
            continue
        transactions.append({
            "date": date,
            "code": code,
            "shares": shares,
            "price": price,
            "total": shares * price,
        })

    return officer_title, issuer_name, owner_name, transactions


def format_email_body(notifications):
    lines = []
    for n in notifications:
        lines.append(
            f"{n['company']} ({n['ticker']}) — {n['owner']}, {n['title']}\n"
            f"  {TRANSACTION_CODES[n['code']]}: {n['shares']:,.0f} shares "
            f"@ ${n['price']:,.2f} = ${n['total']:,.2f}\n"
            f"  Transaction date: {n['date']}\n"
            f"  Filing: {n['href']}\n"
        )
    return "\n".join(lines)


def send_email(notifications):
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY not set; skipping email send.", file=sys.stderr)
        return
    body_text = format_email_body(notifications)
    resp = requests.post(
        RESEND_API_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "from": "Insider Trading Bot <onboarding@resend.dev>",
            "to": [NOTIFY_EMAIL],
            "subject": f"Insider Trade Alert: {len(notifications)} new filing(s)",
            "text": body_text,
        },
        timeout=30,
    )
    resp.raise_for_status()


def check_company(company_name, cik, ticker, seen_accessions):
    new_notifications = []
    newly_seen = []
    for filing in fetch_filing_list(cik):
        accession = filing["accession"]
        if accession in seen_accessions:
            continue

        xml_url = find_ownership_xml_url(cik, accession)
        if xml_url is None:
            continue
        officer_title, issuer_name, owner_name, transactions = parse_ownership_xml(
            get(xml_url).content
        )
        if not title_matches(officer_title) or not transactions:
            continue

        newly_seen.append(accession)
        for tx in transactions:
            new_notifications.append({
                "company": company_name,
                "ticker": ticker,
                "owner": owner_name,
                "title": officer_title,
                "href": filing["href"],
                **tx,
            })

    return new_notifications, newly_seen


def main():
    dry_run = "--dry-run" in sys.argv
    state = load_state()
    all_notifications = []

    for company_name, info in COMPANIES.items():
        cik = info["cik"]
        seen = set(state.get(cik, []))
        notifications, newly_seen = check_company(company_name, cik, info["ticker"], seen)
        all_notifications.extend(notifications)
        if not dry_run:
            state.setdefault(cik, [])
            state[cik].extend(newly_seen)

    if all_notifications:
        print(f"Found {len(all_notifications)} qualifying transaction(s):")
        print(format_email_body(all_notifications))
        if not dry_run:
            send_email(all_notifications)
    else:
        print("No new qualifying insider transactions found.")

    if not dry_run:
        save_state(state)


if __name__ == "__main__":
    main()
