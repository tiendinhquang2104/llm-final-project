"""Synthetic dataset generation for the LLM grading challenge.

Modules mirror the pipeline in docs/synth_plan.md. Derive from docs/task1_rulebook.md; the
generator is deliberately split so the deterministic pieces (labeler, taxonomy, compliance,
verify harness, mutators) can be unit-tested without a compiler or an LLM, while the
LLM/compiler-dependent pieces (bases, oracle) take injected backends.
"""
