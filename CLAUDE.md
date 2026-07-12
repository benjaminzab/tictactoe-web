# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A single self-contained static HTML file (`tictactoe.html`) implementing a playable tic-tac-toe game. There is no build step, package manager, bundler, test suite, or server — the file is opened directly in a browser.

## Running / testing changes

Open `tictactoe.html` directly in a browser (e.g. `open tictactoe.html` on macOS) to test changes. There is no dev server, lint, or test command in this repo — verify behavior manually in-browser.

## Git workflow

Whenever changes are made to files in this repo, commit them and push to GitHub immediately afterward — do not wait to be asked and do not pause for confirmation before pushing. Use a concise commit message describing the change.

## Architecture

Everything lives in one file, in three parts:

- **`<style>` (top of file)**: Theming is done entirely through CSS custom properties on `:root`. Light/dark values are defined three times — a base `:root` block, a `@media (prefers-color-scheme: dark)` override, and explicit `:root[data-theme="dark"]` / `:root[data-theme="light"]` overrides (for a manual theme toggle stamped on the root element). When changing colors, update all relevant blocks, not just one.
- **Two `@font-face` families are embedded as base64 `data:` URIs** directly in the CSS (Shippori Mincho for display/headings, Zen Kaku Gothic New for body/UI text) — there are no external font requests. If re-generating these, only the Latin-subset woff2 files are needed (the full family files include large CJK glyph sets that aren't used here).
- **Markup (`<main class="scroll">`)**: static shell (title, status line, mode toggle, score ledger) plus a `#cells` container that JS populates with 9 button elements, and an SVG overlay (`#strike`) used to draw the winning-line strike-through.
- **`<script>` (IIFE at bottom)**: all game logic.
  - `board` is a flat 9-element array; `WIN_LINES` lists the 8 index triples that count as a win.
  - `placeMark` / `checkWinner` / `endGame` drive turn-taking, win/draw detection, and score updates (`scores.X/O/D`).
  - Marks and the winning strike are drawn as SVG paths and animated by measuring `getTotalLength()` and animating `stroke-dashoffset` via the Web Animations API (`animateDraw`, `drawStrike`); this is skipped (drawn instantly) when `prefers-reduced-motion: reduce` is set.
  - The computer opponent (`Vs Computer` mode) is a plain minimax (`minimax` / `bestMove`) that always plays optimally as `O`; it's a fixed-depth full search (board is only 9 cells) with no pruning or difficulty levels.
