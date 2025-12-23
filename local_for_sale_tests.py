#!/usr/bin/env python
"""
Local human-in-the-loop runner for Craigslist "for sale" scenarios.

- No Hugging Face dependency
- Dataset rows are defined locally
- Uses the same evaluator + agent loop as demo.py
"""

import asyncio
import json
from typing import Dict, Any

from playwright.async_api import Page, async_playwright

from navi_bench.base import DatasetItem, instantiate


# ============================================================================
# LOCAL DATASET ROWS (add more here)
# ============================================================================

LOCAL_DATASET_ROWS: list[Dict[str, Any]] = [
    {
        "task_id": "navi_bench/craigslist/for_sale_complex/9",
        "task_generation_config_json": json.dumps(
            {
                "_target_": "navi_bench.craigslist.craigslist_url_match.generate_task_config",
                "url": "https://sfbay.craigslist.org/search/sss",
                "task": "Find items with images priced between $25 and $75, sorted by lowest price.",
                "location": "San Francisco, CA, United States",
                "timezone": "America/Los_Angeles",
                "gt_urls": [
                    [
                        "https://sfbay.craigslist.org/search/sss?hasPic=1&min_price=25&max_price=75&sort=priceasc#search=2~gallery~0"
                    ]
                ],
            }
        ),
        "env": "real",
        "domain": "craigslist",
        "l1_category": "realestate",
        "l2_category": "for_sale_complex",
        "suggested_difficulty": "hard",
        "suggested_hint": None,
        "suggested_max_steps": 0,
        "suggested_split": "validation",
        "metadata_json": None
    }

]

# ============================================================================
# AGENT LOOP ATTACHMENT (same logic as demo.py)
# ============================================================================

async def attach_human_agent_loop(page: Page, evaluator) -> None:
    async def on_navigation():
        try:
            await evaluator.update(url=page.url, page=page)
        except Exception as e:
            print(f"[WARN] evaluator.update(url={page.url!r}) failed: {e}")

    page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))


# ============================================================================
# RUN A SINGLE LOCAL TASK
# ============================================================================

async def run_local_task(dataset_row: Dict[str, Any]) -> None:
    # Validate and generate task config
    dataset_item = DatasetItem.model_validate(dataset_row)
    task_config = dataset_item.generate_task_config()

    # Instantiate evaluator
    evaluator = instantiate(task_config.eval_config)

    print("\n" + "=" * 80)
    print("TASK")
    print("=" * 80)
    print(f"Task ID: {dataset_row['task_id']}")
    print(f"URL:     {task_config.url}")
    print(f"Task:    {task_config.task}")
    print("=" * 80 + "\n")

    input("Press Enter when ready to start the browser...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1280, "height": 720})
        page = await context.new_page()

        await page.goto(task_config.url, timeout=60_000, wait_until="load")

        print(
            "\nBrowser opened.\n"
            "➡ You are now the agent.\n"
            "➡ Perform the task using the UI.\n"
            "➡ When done, return here and press ENTER.\n"
        )

        # Reset evaluator and record initial state
        await evaluator.reset()
        await evaluator.update(url=task_config.url, page=page)

        # Attach navigation listener
        await attach_human_agent_loop(page, evaluator)

        # Wait for human completion
        await asyncio.to_thread(
            input, "\nPress Enter when you've completed the task... "
        )

        # Final update
        try:
            await evaluator.update(url=page.url, page=page)
        except Exception as e:
            print(f"[WARN] Final evaluator.update failed: {e}")

        # Compute result
        print("\nComputing evaluation result...\n")
        result = await evaluator.compute()

        await context.close()
        await browser.close()

    # Print result
    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Score: {result.score}")
    print(f"Reasoning: {result.reasoning}")
    print("=" * 80 + "\n")


# ============================================================================
# MAIN ENTRYPOINT
# ============================================================================

async def main():
    for row in LOCAL_DATASET_ROWS:
        await run_local_task(row)


if __name__ == "__main__":
    asyncio.run(main())
