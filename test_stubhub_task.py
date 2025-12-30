#!/usr/bin/env python
"""
Local human-in-the-loop runner for StubHub ticket availability scenarios.

- No Hugging Face dependency
- Dataset rows defined locally
- Uses the same evaluator + agent loop pattern as demo.py
"""

import asyncio
import json
from typing import Dict, Any, List

from playwright.async_api import Page, async_playwright
from navi_bench.base import DatasetItem, instantiate


# =============================================================================
# LOCAL STUBHUB DATASET ROWS
# =============================================================================

LOCAL_DATASET_ROWS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------------------
    # 1. Concert — basic availability
    # -------------------------------------------------------------------------
    # {
    #     "task_id": "navi_bench/stubhub/concerts/any_sd_sq_price/0",
    #     "task_generation_config_json": json.dumps(
    #         {
    #             "_target_": "navi_bench.stubhub.stubhub_task_generation.generate_task_config_deterministic",
    #             "mode": "any",
    #             "url": "https://www.stubhub.com/",
    #             "task": (
    #                 "Check if tickets are available for Sonu Nigam in Pune on "
    #                 "January 10, 2026 for 2 people under $150."
    #             ),
    #             "queries": [
    #                 [
    #                     {
    #                         "event_names": ["sonu nigam"],
    #                         "dates": ["2026-01-10"],
    #                         "venues": ["pune"],
    #                         "ticket_quantities": [2],
    #                         "min_price": 0,
    #                         "max_price": 150,
    #                     }
    #                 ]
    #             ],
    #             "location": "Pune, Maharashtra, India",
    #             "timezone": "India/Mumbai",
    #         }
    #     ),
    #     "env": "real",
    #     "domain": "stubhub",
    #     "l1_category": "entertainment",
    #     "l2_category": "concerts",
    # },

    # -------------------------------------------------------------------------
    # 2. Sports — multiple quantities
    # -------------------------------------------------------------------------
    {
        "task_id": "navi_bench/stubhub/sports/any_md_mq_price/0",
        "task_generation_config_json": json.dumps(
            {
                "_target_": "navi_bench.stubhub.stubhub_task_generation.generate_task_config_deterministic",
                "mode": "any",
                "url": "https://www.stubhub.com",
                "task": (
                    "Check ticket availability for the Los Angeles Lakers game "
                    "in Los Angeles tomorrow for 2 to 4 people under $200."
                ),
                "queries": [
                    [
                        {
                            "event_names": ["lakers"],
                            "ticket_quantities": [8],
                            "min_price": 0,
                            "max_price": 200,
                            "domain": ["sports"],
                        }
                    ]
                ],
                "location": "Los Angeles, CA, United States",
                "timezone": "America/Los_Angeles",
            }
        ),
        "env": "real",
        "domain": "stubhub",
        "l1_category": "entertainment",
        "l2_category": "entertainment",
    },

    # # -------------------------------------------------------------------------
    # # 3. Theatre — sold-out allowed
    # # -------------------------------------------------------------------------
    # {
    #     "task_id": "navi_bench/stubhub/theatre/any_md_sq_price/0",
    #     "task_generation_config_json": json.dumps(
    #         {
    #             "_target_": "navi_bench.stubhub.stubhub_task_generation.generate_task_config_deterministic",
    #             "mode": "any",
    #             "url": "https://www.stubhub.com",
    #             "task": (
    #                 "Check if tickets are available for Hamilton in Chicago "
    #                 "this weekend for 2 people under $300."
    #             ),
    #             "queries": [
    #                 [
    #                     {
    #                         "event_names": ["hamilton"],
    #                         "ticket_quantities": [2],
    #                         "min_price": 0,
    #                         "max_price": 300,
    #                         "domain": ["theatre"],
    #                     }
    #                 ]
    #             ],
    #             "location": "Chicago, IL, United States",
    #             "timezone": "America/Chicago",
    #         }
    #     ),
    #     "env": "real",
    #     "domain": "stubhub",
    #     "l1_category": "entertainment",
    #     "l2_category": "theatre",
    # },

    # # -------------------------------------------------------------------------
    # # 4. Festival — multi-day
    # # -------------------------------------------------------------------------
    # {
    #     "task_id": "navi_bench/stubhub/festivals/any_md_sq_price/0",
    #     "task_generation_config_json": json.dumps(
    #         {
    #             "_target_": "navi_bench.stubhub.stubhub_task_generation.generate_task_config_deterministic",
    #             "mode": "any",
    #             "url": "https://www.stubhub.com",
    #             "task": (
    #                 "Check if tickets are available for Coachella for 1 person "
    #                 "under $500."
    #             ),
    #             "queries": [
    #                 [
    #                     {
    #                         "event_names": ["coachella"],
    #                         "ticket_quantities": [1],
    #                         "min_price": 0,
    #                         "max_price": 500,
    #                         "domain": ["festivals"],
    #                     }
    #                 ]
    #             ],
    #             "location": "Indio, CA, United States",
    #             "timezone": "America/Los_Angeles",
    #         }
    #     ),
    #     "env": "real",
    #     "domain": "stubhub",
    #     "l1_category": "entertainment",
    #     "l2_category": "festivals",
    # },

    # # -------------------------------------------------------------------------
    # # 5. Concert — ALL mode (stress test)
    # # -------------------------------------------------------------------------
    # {
    #     "task_id": "navi_bench/stubhub/concerts/all_sd_sq_price/0",
    #     "task_generation_config_json": json.dumps(
    #         {
    #             "_target_": "navi_bench.stubhub.stubhub_task_generation.generate_task_config_deterministic",
    #             "mode": "all",
    #             "url": "https://www.stubhub.com",
    #             "task": (
    #                 "Check all ticket availability for Taylor Swift in New York "
    #                 "on January 20, 2025 for 2 people under $300."
    #             ),
    #             "queries": [
    #                 [
    #                     {
    #                         "event_names": ["taylor swift"],
    #                         "ticket_quantities": [2],
    #                         "min_price": 0,
    #                         "max_price": 300,
    #                         "domain": ["concerts"],
    #                     }
    #                 ]
    #             ],
    #             "location": "New York, NY, United States",
    #             "timezone": "America/New_York",
    #         }
    #     ),
    #     "env": "real",
    #     "domain": "stubhub",
    #     "l1_category": "entertainment",
    #     "l2_category": "concerts",
    # },
]


# =============================================================================
# AGENT LOOP ATTACHMENT (same as demo.py)
# =============================================================================

async def attach_human_agent_loop(page: Page, evaluator) -> None:
    async def on_navigation():
        try:
            await evaluator.update(url=page.url, page=page)
        except Exception as e:
            print(f"[WARN] evaluator.update(url={page.url!r}) failed: {e}")

    page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))


#################################################################################
async def attach_to_page(page: Page, evaluator) -> None:
    async def on_navigation():
        try:
            await evaluator.update(url=page.url, page=page)
        except Exception as e:
            print(f"[WARN] evaluator.update(url={page.url!r}) failed: {e}")

    page.on("framenavigated", lambda frame: asyncio.create_task(on_navigation()))

async def handle_new_page(new_page: Page, evaluator) -> None:
    await new_page.wait_for_load_state("load")
    print(f"[INFO] New tab detected: {new_page.url}")

    # Attach navigation listener
    await attach_to_page(new_page, evaluator)

    # Take an immediate snapshot
    # try:
    #     await evaluator.update(url=new_page.url, page=new_page)
    # except Exception as e:
    #     print(f"[WARN] evaluator.update(new tab) failed: {e}")


# =============================================================================
# RUN A SINGLE LOCAL TASK
# =============================================================================

async def run_local_task(dataset_row: Dict[str, Any]) -> None:
    dataset_item = DatasetItem.model_validate(dataset_row)
    task_config = dataset_item.generate_task_config()
    evaluator = instantiate(task_config.eval_config)

    print("\n" + "=" * 80)
    print("TASK")
    print("=" * 80)
    print(f"Task ID: {dataset_row['task_id']}")
    print(f"URL:     {task_config.url}")
    print(f"Task:    {task_config.task}")
    print("=" * 80 + "\n")

    input("Press Enter when ready to start the browser...")

    # async with async_playwright() as p:
    #     browser = await p.chromium.launch(headless=False)
    #     context = await browser.new_context(
    #         viewport={"width": 1280, "height": 720}
    #         )
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="en-US",
            timezone_id="America/Los_Angeles",
        )
        
        # Remove the webdriver property that exposes automation
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        page = await context.new_page()
        context.on(
            "page",
            lambda new_page: asyncio.create_task(
                handle_new_page(new_page, evaluator)
            )
        )

        await page.goto(task_config.url, timeout=60_000, wait_until="load")

        print(
            "\nBrowser opened.\n"
            "➡ You are now the agent.\n"
            "➡ Complete the task using the StubHub UI.\n"
            "➡ When done, return here and press ENTER.\n"
        )

        await evaluator.reset()
        # await evaluator.update(url=task_config.url, page=page)
        # await attach_human_agent_loop(page, evaluator)
        await attach_to_page(page, evaluator)

        await asyncio.to_thread(
            input, "\nPress Enter when you've completed the task... "
        )

        try:
            await evaluator.update(url=page.url, page=page)
        except Exception as e:
            print(f"[WARN] Final evaluator.update failed: {e}")

        print("\nComputing evaluation result...\n")
        result = await evaluator.compute()

        await context.close()
        await browser.close()

    print("=" * 80)
    print("RESULT")
    print("=" * 80)
    print(f"Score: {result.score}")
    print(f"is_query_covered: {result.is_query_covered}")
    print("=" * 80 + "\n")


# =============================================================================
# MAIN
# =============================================================================

async def main():
    for row in LOCAL_DATASET_ROWS:
        await run_local_task(row)


if __name__ == "__main__":
    asyncio.run(main())
