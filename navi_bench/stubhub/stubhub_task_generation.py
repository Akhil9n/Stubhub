# navi_bench/stubhub/stubhub_task_generation.py

from navi_bench.base import BaseTaskConfig, UserMetadata, get_import_path
from navi_bench.stubhub.stubhub_info_gathering import StubHubInfoGathering


def generate_task_config_deterministic(
    *,
    mode: str,
    task: str,
    url: str,
    queries: list[list[dict]],
    location: str,
    timezone: str,
) -> BaseTaskConfig:
    """
    Deterministic task config generator for StubHub tasks.
    """

    user_metadata = UserMetadata(
        location=location,
        timezone=timezone,
    )

    eval_config = {
        "_target_": get_import_path(StubHubInfoGathering),
        "queries": queries,
    }

    return BaseTaskConfig(
        task=task,
        url=url,
        user_metadata=user_metadata,
        eval_config=eval_config,
    )
