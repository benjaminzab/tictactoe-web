# Insider Trading Bot

Checks SEC EDGAR every 4 hours (via GitHub Actions, see
`../.github/workflows/insider-trading-check.yml`) for new Form 4 filings
reporting an open-market **purchase or sale** of stock by a CEO, CFO, CTO,
VP, President, or Chairman at Nvidia, Amazon, SolarEdge, or Digi Power X.
When one is found, it emails the details (date, shares, price, total
dollar value) to benjamin.472006@gmail.com via [Resend](https://resend.com).

## One-time setup

1. **Sign up for Resend** at https://resend.com using
   **benjamin.472006@gmail.com** as the account email.
   - On the free tier, without a verified custom domain, Resend only lets
     you send *to* the address you signed up with, from their shared
     sandbox address `onboarding@resend.dev`. Since all alerts go to that
     same address, this works with no domain setup.
2. Create an API key: Resend dashboard → **API Keys** → **Create API Key**.
3. Add it as a GitHub Actions secret named `RESEND_API_KEY`:
   ```
   gh secret set RESEND_API_KEY --repo <owner>/<repo>
   ```
   (or via GitHub: repo **Settings → Secrets and variables → Actions →
   New repository secret**).

## Running a manual check

```
gh workflow run insider-trading-check.yml
gh run watch
```

## Running locally

```
pip install -r requirements.txt
python check_filings.py --dry-run   # fetch + print, no email, no state write
RESEND_API_KEY=... python check_filings.py   # real run
```

## Adjusting scope

- Companies tracked: edit the `COMPANIES` dict in `check_filings.py`
  (needs each company's SEC CIK — look it up at
  https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=NAME&type=4).
- Roles tracked: edit `TITLE_KEYWORDS` in `check_filings.py`.
- Only Form 4 transaction codes `P` (open-market purchase) and `S`
  (open-market sale) trigger a notification — option exercises, RSU
  vesting, gifts, and tax-withholding dispositions are ignored. Edit
  `TRANSACTION_CODES` to change this.
