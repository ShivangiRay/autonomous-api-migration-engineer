# ADR 0001: Deterministic Graph-Orchestrated Agents

## Status

Accepted

## Context

The product needs multi-agent reasoning artifacts without depending on paid external APIs for core functionality.

## Decision

Use an explicit graph workflow abstraction that mirrors LangGraph-style nodes and edges. Each agent receives typed inputs, writes typed outputs, and appends audit events.

## Consequences

- The bootstrap is testable and deterministic.
- A LangGraph implementation can replace the local graph without changing agent boundaries.
- Audit trails and provenance are first-class from the first version.

