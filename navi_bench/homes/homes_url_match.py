"""
Homes.com URL Match Verifier (Universal Edition)

Handles both Path-Based Slugs AND Query Parameters.
Fixes false positives by ensuring filters are extracted from all URL formats.
"""

import re
from typing import Any, Dict, Optional, Tuple, List
from urllib.parse import parse_qs, urlparse
from pydantic import BaseModel
from navi_bench.base import BaseMetric


class HomesVerifierResult(BaseModel):
    score: float
    match: bool
    agent_url: str
    ground_truth_url: str
    details: dict


class HomesUrlMatch(BaseMetric):
    """
    Universal Homes.com Verifier.
    """

    def __init__(
        self,
        ground_truth_url: str,
        *,
        strict_location: bool = True,
        strict_filters: bool = True
    ):
        self.ground_truth_url = ground_truth_url
        self.strict_location = strict_location
        self.strict_filters = strict_filters
        self._agent_url: Optional[str] = None

    async def update(self, *, url: Optional[str] = None, **kwargs) -> None:
        if url:
            self._agent_url = url

    async def compute(self) -> HomesVerifierResult:
        if not self._agent_url:
            return HomesVerifierResult(
                score=0.0, match=False, agent_url="", 
                ground_truth_url=self.ground_truth_url, 
                details={"error": "No agent URL provided"}
            )
        
        match, details = self._urls_match(self._agent_url, self.ground_truth_url)
        
        return HomesVerifierResult(
            score=1.0 if match else 0.0,
            match=match,
            agent_url=self._agent_url,
            ground_truth_url=self.ground_truth_url,
            details=details
        )

    def _parse_homes_url(self, url: str) -> Dict[str, Any]:
        """
        Parses filters from URL path AND query parameters.
        """
        result = {
            "location": None,
            "filters": {}
        }

        if not url:
            return result

        parsed = urlparse(url)
        path_segments = [s for s in parsed.path.split("/") if s]
        
        # --- 1. LOCATION EXTRACTION ---
        # Heuristic: First segment that isn't a transaction type
        ignore_slugs = {"homes-for-sale", "homes-for-rent", "sold", "new-homes"}
        for segment in path_segments:
            if segment not in ignore_slugs and not any(char.isdigit() for char in segment):
                # Simple check: locations usually don't have numbers (except zip codes)
                result["location"] = segment.replace("-", " ").lower()
                break

        # --- 2. PATH SLUG EXTRACTION (The "Pretty" URL filters) ---
        for segment in path_segments:
            # Price: p-500k, p-1m-5m
            if segment.startswith("p-"):
                # Clean up: p-500k -> 500k
                val = segment[2:].replace("k", "000").replace("m", "000000").replace("+", "")
                if "-" in val:
                    try:
                        min_p, max_p = val.split("-")
                        result["filters"]["price_min"] = self._clean_num(min_p)
                        result["filters"]["price_max"] = self._clean_num(max_p)
                    except: pass
                else:
                    # Ambiguous: usually p-500k means max or min depending on context
                    # Homes.com usually treats single value as MAX unless '+' was present
                    result["filters"]["price_min"] = self._clean_num(val)

            # Bedrooms: 3-bed, 3-bedroom, 3-to-5-bedroom
            bed_match = re.search(r"(\d+)(?:-to-(\d+))?-bed", segment)
            if bed_match:
                result["filters"]["beds_min"] = int(bed_match.group(1))
                if bed_match.group(2):
                    result["filters"]["beds_max"] = int(bed_match.group(2))

            # Bathrooms: 2-bath, 2-ba
            bath_match = re.search(r"(\d+(?:\.\d+)?)-ba", segment)
            if bath_match:
                result["filters"]["baths_min"] = float(bath_match.group(1))

        # --- 3. QUERY PARAM EXTRACTION (The "Real" URL filters) ---
        # These override path slugs if present
        qs = parse_qs(parsed.query)
        
        if "price-min" in qs: result["filters"]["price_min"] = self._clean_num(qs["price-min"][0])
        if "price-max" in qs: result["filters"]["price_max"] = self._clean_num(qs["price-max"][0])
        if "beds-min" in qs: result["filters"]["beds_min"] = self._clean_num(qs["beds-min"][0])
        if "beds-max" in qs: result["filters"]["beds_max"] = self._clean_num(qs["beds-max"][0])
        if "baths-min" in qs: result["filters"]["baths_min"] = float(qs["baths-min"][0])

        return result

    def _clean_num(self, val: str) -> int:
        try:
            clean = str(val).lower().replace(",", "").replace("$", "").replace("+", "")
            return int(float(clean))
        except:
            return 0

    def _urls_match(self, agent_url: str, gt_url: str) -> Tuple[bool, Dict]:
        agent_parts = self._parse_homes_url(agent_url)
        gt_parts = self._parse_homes_url(gt_url)
        
        details = {
            "agent_parsed": agent_parts,
            "gt_parsed": gt_parts,
            "mismatches": []
        }

        # Check Location
        if self.strict_location and gt_parts["location"]:
            a_loc = agent_parts["location"] or ""
            g_loc = gt_parts["location"] or ""
            if g_loc not in a_loc and a_loc not in g_loc:
                details["mismatches"].append({
                    "field": "location",
                    "agent": a_loc,
                    "expected": g_loc
                })
                return False, details

        # Check Filters
        if self.strict_filters:
            # If GT has no filters, warn but pass (unless empty GT is invalid for the task)
            if not gt_parts["filters"]:
                pass 
                
            for key, expected_val in gt_parts["filters"].items():
                agent_val = agent_parts["filters"].get(key)
                
                if agent_val != expected_val:
                    details["mismatches"].append({
                        "field": key,
                        "agent": agent_val,
                        "expected": expected_val
                    })
                    return False, details

        return True, details