import json
import asyncio
import sys
from pathlib import Path
from typing import List

# Import your existing verifier
try:
    from homes_url_match import HomesUrlMatch
except ImportError:
    sys.path.append(str(Path(__file__).parent))
    from homes_url_match import HomesUrlMatch

async def run_verification_tests(json_path: str):
    print(f"📂 Loading tasks from: {json_path}")
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        print("❌ Error: JSON file not found.")
        return

    total_tests = 0
    passed_tests = 0
    failed_tests = 0

    print(f"\n🚀 Running Verification on {len(tasks)} Tasks...\n")

    for task in tasks:
        task_id = task.get("task_id", "Unknown ID")
        config = task.get("task_generation_config_json", {})
        
        # Extract GT URLs
        raw_gt = config.get("gt_urls", [])
        gt_urls_flat = []
        for item in raw_gt:
            if isinstance(item, list):
                gt_urls_flat.extend(item)
            elif isinstance(item, str):
                gt_urls_flat.append(item)
        
        if not gt_urls_flat:
            print(f"⚠️ Skipping {task_id}: No GT URLs found.")
            continue

        # We use the FIRST valid GT URL as the "Standard"
        ground_truth_url = gt_urls_flat[0]
        
        print(f"🔹 Task: {task_id}")
        
        for test_url in gt_urls_flat:
            total_tests += 1
            
            # Initialize verifier
            verifier = HomesUrlMatch(ground_truth_urls=ground_truth_url)
            await verifier.update(url=test_url)
            result = await verifier.compute()
            
            if result.match:
                passed_tests += 1
                print(f"   ✅ PASS")
                # --- NEW: Print the internal dictionary ---
                print(f"      Parsed Data: {result.details['gt_parsed']}")
                print("-" * 50)
            else:
                failed_tests += 1
                print(f"   ❌ FAIL: {test_url}")
                print(f"      Reason: {result.details.get('mismatches')}")
                print(f"      Parsed Data: {result.details['gt_parsed']}")
                print("-" * 50)

    print("\n📊 SUMMARY")
    print(f"Total URL Checks: {total_tests}")
    print(f"Passed: {passed_tests}")
    print(f"Failed: {failed_tests}")
    
    if total_tests > 0:
        accuracy = (passed_tests / total_tests) * 100
        print(f"Accuracy: {accuracy:.2f}%")

if __name__ == "__main__":
    # Assumes 'homes_tasks.json' is in the same directory
    asyncio.run(run_verification_tests("homes/homes_tasks.json"))