"""Drive the running app with a headless browser: smoke-test every screen and save screenshots.

Usage:  python scripts/capture_screenshots.py [base_url]     (server must be running)
Requires: pip install playwright   and a Chrome/Chromium binary (CHROME_PATH or /usr/bin/google-chrome).
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
CHROME = os.environ.get("CHROME_PATH", "/usr/bin/google-chrome")

errors = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        errors.append(msg)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
    page = browser.new_page(viewport={"width": 1360, "height": 900}, device_scale_factor=1.5)
    console = []
    page.on("console", lambda m: console.append(m.text) if m.type in ("error",) else None)
    page.on("pageerror", lambda e: console.append(str(e)))

    # ---- Home
    page.goto(BASE + "/")
    page.wait_for_selector("text=Connect-N")
    page.screenshot(path=OUT / "home.png")
    check(page.locator("text=Play vs AI").count() > 0, "home renders")

    # ---- Human vs AI
    page.goto(BASE + "/play")
    page.wait_for_selector("svg[role=img]")
    page.wait_for_selector("text=Your turn")
    board = page.locator("svg[role=img]").first
    box = board.bounding_box()
    # click the middle column (centre x), anywhere vertically
    page.mouse.click(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.wait_for_selector("text=Selected move", timeout=20000)
    page.wait_for_selector("text=Your turn", timeout=20000)
    check(page.locator("text=Nodes explored").count() > 0, "AI insights shown after the AI move")
    page.wait_for_timeout(500)  # input is (correctly) ignored while a move is in flight
    page.mouse.click(box["x"] + box["width"] * 0.35, box["y"] + box["height"] / 2)
    page.wait_for_function("document.querySelector('[role=status]')?.innerText.includes('move 4')", timeout=20000)
    page.wait_for_selector("text=Your turn", timeout=20000)
    page.mouse.move(5, 5)
    page.wait_for_timeout(900)  # let the drop animation finish
    page.screenshot(path=OUT / "play_human_vs_ai.png")
    status = page.locator("[role=status]").first.inner_text()
    check("move 4" in status, f"4 plies played (status: {status.splitlines()[-1]})")
    # illegal-move robustness: fill column then click again is covered by engine tests

    # ---- Arena: watch a match
    page.goto(BASE + "/arena")
    page.wait_for_selector("text=Start match")
    page.get_by_role("button", name="Start match").click()
    page.wait_for_function("document.querySelector('[role=status]')?.innerText.match(/move (\\d+)/) && Number(document.querySelector('[role=status]').innerText.match(/move (\\d+)/)[1]) >= 8", timeout=60000)
    page.get_by_role("button", name="Pause").click()
    page.wait_for_timeout(900)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=OUT / "arena_live_match.png", full_page=True)
    # run a series
    page.get_by_role("button", name="Play 10 games").click()
    page.wait_for_selector("text=Last series", timeout=120000)
    page.screenshot(path=OUT / "arena_series.png", full_page=True)
    check(page.locator("text=Scoreboard").count() > 0, "arena scoreboard + series")

    # ---- AI vs AI on the Play page
    page.goto(BASE + "/play")
    page.get_by_role("tab", name="AI vs AI").click()
    page.get_by_role("button", name="Start match").click()
    page.wait_for_function("Number((document.querySelector('[role=status]')?.innerText.match(/move (\\d+)/)||[0,0])[1]) >= 6", timeout=60000)
    page.screenshot(path=OUT / "play_ai_vs_ai.png")

    # ---- Analytics
    page.goto(BASE + "/analytics")
    page.wait_for_selector("text=Win-rate comparison", timeout=20000)
    page.wait_for_selector(".recharts-bar-rectangle", timeout=20000)
    page.wait_for_timeout(1500)
    page.screenshot(path=OUT / "analytics_dashboard.png", full_page=True)
    check(page.locator("svg.recharts-surface").count() >= 8, f"charts rendered ({page.locator('svg.recharts-surface').count()})")

    # ---- Insights
    page.goto(BASE + "/insights")
    page.wait_for_selector("text=Selected move", timeout=30000)
    box = page.locator("svg[role=img]").first.bounding_box()
    for frac in (0.5, 0.5, 0.36):
        page.mouse.click(box["x"] + box["width"] * frac, box["y"] + box["height"] / 2)
        page.wait_for_timeout(700)
    page.wait_for_selector("text=Heuristic evaluation", timeout=30000)
    page.wait_for_timeout(1200)
    page.screenshot(path=OUT / "ai_insights.png", full_page=True)
    check(page.locator("text=Own open windows").count() > 0, "insights heuristic breakdown")

    # ---- Mobile layout
    mob = browser.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    mob.goto(BASE + "/play")
    mob.wait_for_selector("svg[role=img]")
    mob.wait_for_timeout(800)
    mob.screenshot(path=OUT / "mobile_play.png")
    overflow = mob.evaluate("document.documentElement.scrollWidth - window.innerWidth")
    check(overflow <= 1, f"no horizontal overflow on mobile (delta {overflow}px)")

    check(not console, f"no console errors: {console[:3]}")
    browser.close()

print("\nFAILURES:", errors if errors else "none")
sys.exit(1 if errors else 0)
