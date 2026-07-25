"""
federation — Jit-'s adapter for the cross-repository federation.

This does NOT merge Jit into the other repos. It makes the Jit API a
*federated service*: it self-describes its capabilities in a manifest, keeps
a tamper-evident audit ledger of federation activity, and exposes the small
``/federation/*`` surface the Neural Swarm hub (jfjf) uses to register,
health-check, and forensically verify this service.

The hub half (mediator agent + forensic matrix) lives in the jfjf repo; this
package is intentionally the lightweight service-side counterpart. ``protocol``
is vendored byte-compatible with the hub so the hub can verify Jit's chain.
"""

from __future__ import annotations

from jit.federation import protocol  # noqa: F401

__all__ = ["protocol"]
