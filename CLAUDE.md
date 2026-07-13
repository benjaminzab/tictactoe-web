# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

This repo holds two unrelated projects that happen to share git history:

- **`tictactoe.html`** — a self-contained static tic-tac-toe game.
- **`insider-trading-bot/`** — a Python script + GitHub Actions workflow that polls SEC EDGAR for insider stock trades and emails alerts.

They share no code; each is documented in its own section below.

## Git workflow

Whenever changes are made to files in this repo, commit them and push to GitHub immediately afterward — do not wait to be asked and do not pause for confirmation before pushing. Use a concise commit message describing the change.

## Tic-tac-toe game (`tictactoe.html`)

A single self-contained static HTML file implementing a playable tic-tac-toe game. There is no build step, package manager, bundler, test suite, or server — the file is opened directly in a browser.

### Running / testing changes

Open `tictactoe.html` directly in a browser (e.g. `open tictactoe.html` on macOS) to test changes. There is no dev server, lint, or test command in this repo — verify behavior manually in-browser.

### Architecture

Everything lives in one file, in three parts:

- **`<style>` (top of file)**: Theming is done entirely through CSS custom properties on `:root`. Light/dark values are defined three times — a base `:root` block, a `@media (prefers-color-scheme: dark)` override, and explicit `:root[data-theme="dark"]` / `:root[data-theme="light"]` overrides (for a manual theme toggle stamped on the root element). When changing colors, update all relevant blocks, not just one.
- **Two `@font-face` families are embedded as base64 `data:` URIs** directly in the CSS (Shippori Mincho for display/headings, Zen Kaku Gothic New for body/UI text) — there are no external font requests. If re-generating these, only the Latin-subset woff2 files are needed (the full family files include large CJK glyph sets that aren't used here).
- **Markup (`<main class="scroll">`)**: static shell (title, status line, mode toggle, score ledger) plus a `#cells` container that JS populates with 9 button elements, and an SVG overlay (`#strike`) used to draw the winning-line strike-through.
- **`<script>` (IIFE at bottom)**: all game logic.
  - `board` is a flat 9-element array; `WIN_LINES` lists the 8 index triples that count as a win.
  - `placeMark` / `checkWinner` / `endGame` drive turn-taking, win/draw detection, and score updates (`scores.X/O/D`).
  - Marks and the winning strike are drawn as SVG paths and animated by measuring `getTotalLength()` and animating `stroke-dashoffset` via the Web Animations API (`animateDraw`, `drawStrike`); this is skipped (drawn instantly) when `prefers-reduced-motion: reduce` is set.
  - The computer opponent (`Vs Computer` mode) is a plain minimax (`minimax` / `bestMove`) that always plays optimally as `O`; it's a fixed-depth full search (board is only 9 cells) with no pruning or difficulty levels.

## Insider trading bot (`insider-trading-bot/`)

Checks SEC EDGAR every 4 hours for new Form 4 filings reporting an open-market stock purchase/sale by a CEO, CFO, CTO, VP, President, or Chairman at a fixed list of companies, and emails the details to a fixed recipient via the Resend API. No test suite — verify by running against live SEC EDGAR data.

### Running / testing changes

```
pip install -r insider-trading-bot/requirements.txt
python insider-trading-bot/check_filings.py --dry-run   # fetch + print only; no email, no state.json write
python insider-trading-bot/check_filings.py             # real run; sends email only if RESEND_API_KEY is set
```

To trigger the production workflow manually: `gh workflow run insider-trading-check.yml` then `gh run watch`.

### Architecture

Single script, `check_filings.py` (stdlib + `requests`), run on a schedule by `.github/workflows/insider-trading-check.yml` (cron every 4 hours, plus `workflow_dispatch`):

- `COMPANIES` maps company name → SEC CIK + ticker (currently Nvidia, Amazon, SolarEdge, Digi Power X). Add/remove companies here; look up a CIK via `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company=NAME&type=4`.
- `TITLE_KEYWORDS` — case-insensitive substrings matched against a filing's `officerTitle` to decide whether a reporting owner is a tracked role.
- `TRANSACTION_CODES` — only Form 4 codes `P` (open-market purchase) and `S` (open-market sale) trigger a notification; option exercises, RSU vesting, gifts, and tax-withholding dispositions are deliberately ignored.
- `fetch_filing_list` pulls each issuer's recent Form 4s from SEC EDGAR's `browse-edgar` atom feed. `find_ownership_xml_url` locates the filing's primary ownership XML inside its accession folder by scanning `index.json` rather than assuming a filename — SEC filing agents name this file inconsistently (`ownership.xml`, `primary_doc.xml`, etc). `parse_ownership_xml` extracts officer title, owner name, and non-derivative transactions from that XML.
- `state.json` (committed to the repo) tracks, per CIK, which accession numbers have already produced a notification, so re-runs don't re-notify. Filings that don't match a tracked title or have no qualifying transaction are *not* recorded, so they get re-fetched and re-checked on every subsequent run.
- `send_email` posts to the Resend API. Recipient and sender are hardcoded constants (`NOTIFY_EMAIL`, and Resend's sandbox address `onboarding@resend.dev`) — the sender does not need to be the recipient's own address. Requires `RESEND_API_KEY` in the environment to actually send; without it (e.g. local `--dry-run` or an unset key), notifications are computed and printed but the send is skipped.
- All SEC requests set a descriptive `User-Agent` (`USER_AGENT` constant) — `data.sec.gov`/`www.sec.gov` return 403 without one.
- The GitHub Actions workflow commits any resulting change to `state.json` back to the repo after each run, using its own `GITHUB_TOKEN` (needs `permissions: contents: write`).
