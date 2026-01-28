"""Tests for the health check endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(client: AsyncClient) -> None:
    """GET /health returns 200 status code."""
    response = await client.get("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_returns_healthy_status(client: AsyncClient) -> None:
    """GET /health response contains status='healthy'."""
    response = await client.get("/health")
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_health_endpoint_returns_version(client: AsyncClient) -> None:
    """GET /health response contains version string."""
    response = await client.get("/health")
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


@pytest.mark.asyncio
async def test_health_endpoint_returns_correct_schema(client: AsyncClient) -> None:
    """GET /health response matches HealthResponse schema."""
    response = await client.get("/health")
    data = response.json()

    # Verify only expected keys are present
    assert set(data.keys()) == {"status", "version"}

    # Verify values are correct types
    assert data["status"] == "healthy"
    assert data["version"] == "0.1.0"
