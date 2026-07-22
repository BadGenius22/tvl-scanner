"""job-scanner — daily open-role scanner ranked by personal suitability.

Sibling tool to tvl_scanner in this repo: same architecture (async sources →
scoring formula → ranked markdown + per-record YAML reports), pointed at job
boards instead of DeFi protocols. The profile (`data/profile.yaml`, overridable)
defines what "suitable" means: skills, seniority, location, compensation floor,
and benefits that matter to YOU.
"""

__version__ = "0.1.0"
