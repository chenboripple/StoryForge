"""Proposal management and governance for cross-layer changes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime


class GovernanceAgent:
    """Rule-based governance agent for proposal triage.

    Current policy is intentionally conservative:
    - high risk proposals remain pending
    - low/medium risk with high confidence can be auto-approved
    """

    def evaluate(self, proposal: Dict[str, Any]) -> Dict[str, Any]:
        risk = str(proposal.get("risk_level", "medium")).lower()
        confidence = float(proposal.get("confidence", 0.0))

        if risk == "high":
            return {
                "decision": "pending",
                "reason": "high-risk proposal requires manual review",
            }

        if confidence >= 0.9 and risk in {"low", "medium"}:
            return {
                "decision": "approved",
                "reason": "high-confidence low/medium-risk proposal auto-approved",
            }

        return {
            "decision": "pending",
            "reason": "insufficient confidence for auto-approval",
        }


class ProposalManager:
    """Manages proposal lifecycle and applies governance decisions."""

    def __init__(self, governance_agent: Optional[GovernanceAgent] = None):
        self.governance_agent = governance_agent or GovernanceAgent()

    def review_pending(self, state: Any) -> List[Dict[str, Any]]:
        proposals = list(getattr(state, "proposals", []) or [])
        updates: List[Dict[str, Any]] = []

        for proposal in proposals:
            if proposal.get("status") != "pending":
                continue

            result = self.governance_agent.evaluate(proposal)
            decision = result.get("decision", "pending")
            reason = result.get("reason", "")

            proposal["governance_reason"] = reason
            proposal["reviewed_at"] = datetime.now().isoformat()

            if decision == "approved":
                proposal["status"] = "approved"
                self._apply_proposal_effect(state, proposal)
            elif decision == "rejected":
                proposal["status"] = "rejected"
            else:
                proposal["status"] = "pending"

            updates.append({
                "proposal_id": proposal.get("proposal_id"),
                "status": proposal.get("status"),
                "reason": reason,
            })

        return updates

    def _apply_proposal_effect(self, state: Any, proposal: Dict[str, Any]):
        target = str(proposal.get("target_layer", ""))
        versions = getattr(state, "canonical_versions", None)
        if not isinstance(versions, dict):
            return

        if "volume" in target:
            versions["volume_briefs"] = int(versions.get("volume_briefs", 1)) + 1
        elif "outline" in target:
            versions["outline"] = int(versions.get("outline", 1)) + 1
        elif "character" in target:
            versions["character_profiles"] = int(versions.get("character_profiles", 1)) + 1
        elif "world" in target:
            versions["world_rules"] = int(versions.get("world_rules", 1)) + 1
