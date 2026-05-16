from __future__ import annotations

from libs.common.models import Endpoint, EventTransportRecommendation


def recommend_event_transport(endpoint: Endpoint, similar_case_count: int = 0) -> EventTransportRecommendation:
    text = f"{endpoint.id} {endpoint.operation_id} {endpoint.summary}".lower()
    if any(word in text for word in ["status", "created", "updated", "activated", "disabled"]):
        return EventTransportRecommendation(
            transport="kafka",
            rationale=(
                "Kafka is a better fit because this endpoint represents a durable domain event "
                "that downstream services may replay, audit, and consume independently."
            ),
            confidence=min(0.94, 0.82 + similar_case_count * 0.03),
            tradeoffs=[
                "Requires topic/version governance.",
                "Excellent for ordered event streams and replay.",
                "Less ideal for simple request/reply task dispatch.",
            ],
        )
    return EventTransportRecommendation(
        transport="rabbitmq",
        rationale=(
            "RabbitMQ is a better fit when the conversion is closer to task routing, command dispatch, "
            "or direct worker handoff than long-lived event streaming."
        ),
        confidence=min(0.9, 0.76 + similar_case_count * 0.03),
        tradeoffs=[
            "Good for routing keys, work queues, and retry/dead-letter patterns.",
            "Less natural for event replay and analytics consumers.",
        ],
    )
