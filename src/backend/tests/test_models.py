"""Tests for SQLAlchemy models.

Verifies that models match the PRD schema and have all required fields.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import inspect

from app.db.base import Base
from app.models import (
    CostModel,
    MediaEvent,
    ProcessingStep,
    PromptTemplate,
    Upload,
    UploadPipelineRun,
    User,
)


class TestUserModel:
    """Tests for the User model."""

    def test_user_model_has_required_fields(self) -> None:
        """User model has all required fields from PRD."""
        mapper = inspect(User)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "email",
            "name",
            "auth_provider",
            "auth_provider_id",
            "subscription_tier",
            "subscription_ends_at",
            "stripe_customer_id",
            "created_at",
            "updated_at",
            "deleted_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_user_model_has_correct_types(self) -> None:
        """User model has correct column types."""
        mapper = inspect(User)
        columns = {c.key: c for c in mapper.columns}

        assert columns["id"].type.python_type == UUID
        assert columns["email"].type.length == 255
        assert columns["auth_provider"].type.length == 50
        assert columns["subscription_tier"].type.length == 50

    def test_user_model_has_relationships(self) -> None:
        """User model has all relationships."""
        mapper = inspect(User)
        relationships = {r.key for r in mapper.relationships}

        assert "uploads" in relationships
        assert "pipeline_runs" in relationships
        assert "media_events" in relationships


class TestUploadModel:
    """Tests for the Upload model."""

    def test_upload_model_has_required_fields(self) -> None:
        """Upload model has all required fields from PRD."""
        mapper = inspect(Upload)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "user_id",
            "source_platform",
            "scope",
            "status",
            "total_items",
            "processed_items",
            "file_hash",
            "step_functions_execution_arn",
            "created_at",
            "completed_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_upload_model_has_foreign_key(self) -> None:
        """Upload model has foreign key to users."""
        mapper = inspect(Upload)
        columns = {c.key: c for c in mapper.columns}
        fks = list(columns["user_id"].foreign_keys)
        assert len(fks) == 1
        assert "users.id" in str(fks[0])


class TestUploadPipelineRunModel:
    """Tests for the UploadPipelineRun model."""

    def test_upload_pipeline_run_has_required_fields(self) -> None:
        """UploadPipelineRun model has all required fields from PRD."""
        mapper = inspect(UploadPipelineRun)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "upload_id",
            "user_id",
            "status",
            "started_at",
            "finished_at",
            "total_videos",
            "videos_enriched",
            "videos_media_downloaded",
            "videos_transcribed",
            "videos_vision_done",
            "videos_embedded",
            "videos_complete",
            "videos_failed",
            "total_cost_usd",
            "estimated_completion_at",
            "error_summary",
            "created_at",
            "updated_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_upload_pipeline_run_has_decimal_cost(self) -> None:
        """Cost field uses Decimal for precision."""
        mapper = inspect(UploadPipelineRun)
        columns = {c.key: c for c in mapper.columns}
        assert columns["total_cost_usd"].type.python_type == Decimal


class TestMediaEventModel:
    """Tests for the MediaEvent model."""

    def test_media_event_has_required_fields(self) -> None:
        """MediaEvent model has all required fields from PRD."""
        mapper = inspect(MediaEvent)
        columns = {c.key for c in mapper.columns}

        # Core identifiers
        assert "id" in columns
        assert "user_id" in columns
        assert "upload_id" in columns
        assert "platform" in columns
        assert "platform_id" in columns

        # Processing state
        assert "processing_state" in columns
        assert "processing_substate" in columns

        # Apify enrichment
        assert "caption_text" in columns
        assert "hashtags" in columns
        assert "creator_username" in columns
        assert "play_count" in columns

        # Vision analysis
        assert "visual_tags" in columns
        assert "mood_primary" in columns
        assert "mood_distribution" in columns

        # Search
        assert "full_text" in columns
        assert "embedding_vector" in columns

    def test_media_event_has_vector_column(self) -> None:
        """MediaEvent has pgvector column for embeddings."""
        mapper = inspect(MediaEvent)
        columns = {c.key: c for c in mapper.columns}
        # The column should exist
        assert "embedding_vector" in columns

    def test_media_event_has_unique_constraint(self) -> None:
        """MediaEvent has unique constraint on user_id, platform, platform_id."""
        # Get table constraints
        table = MediaEvent.__table__
        unique_constraints = [
            c for c in table.constraints if c.name == "uq_media_events_user_platform"
        ]
        assert len(unique_constraints) == 1

    def test_media_event_has_indexes(self) -> None:
        """MediaEvent has required indexes."""
        table = MediaEvent.__table__
        index_names = {idx.name for idx in table.indexes}

        expected = {
            "idx_media_events_user",
            "idx_media_events_upload",
            "idx_media_events_platform_id",
            "idx_media_events_processing",
            "idx_media_events_creator",
            "idx_media_events_mood",
            "idx_media_events_interaction",
        }
        assert expected.issubset(index_names), f"Missing indexes: {expected - index_names}"


class TestProcessingStepModel:
    """Tests for the ProcessingStep model."""

    def test_processing_step_has_required_fields(self) -> None:
        """ProcessingStep model has all required fields from PRD."""
        mapper = inspect(ProcessingStep)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "media_event_id",
            "step_type",
            "provider",
            "status",
            "attempt",
            "started_at",
            "finished_at",
            "input_summary",
            "output_summary",
            "error_message",
            "cost_usd",
            "prompt_version",
            "created_at",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_processing_step_has_indexes(self) -> None:
        """ProcessingStep has required indexes."""
        table = ProcessingStep.__table__
        index_names = {idx.name for idx in table.indexes}

        expected = {
            "idx_processing_steps_media",
            "idx_processing_steps_pending",
            "idx_processing_steps_step",
        }
        assert expected.issubset(index_names), f"Missing indexes: {expected - index_names}"


class TestPromptTemplateModel:
    """Tests for the PromptTemplate model."""

    def test_prompt_template_has_required_fields(self) -> None:
        """PromptTemplate model has all required fields from PRD."""
        mapper = inspect(PromptTemplate)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "name",
            "version",
            "model",
            "temperature",
            "max_tokens",
            "system_prompt",
            "user_prompt_template",
            "response_schema",
            "is_active",
            "created_at",
            "notes",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"


class TestCostModel:
    """Tests for the CostModel model."""

    def test_cost_model_has_required_fields(self) -> None:
        """CostModel model has all required fields from PRD."""
        mapper = inspect(CostModel)
        columns = {c.key for c in mapper.columns}

        required = {
            "id",
            "provider",
            "sku",
            "metric",
            "unit_price_usd",
            "effective_from",
            "effective_until",
            "notes",
        }
        assert required.issubset(columns), f"Missing columns: {required - columns}"

    def test_cost_model_has_decimal_price(self) -> None:
        """Price field uses Decimal for precision."""
        mapper = inspect(CostModel)
        columns = {c.key: c for c in mapper.columns}
        assert columns["unit_price_usd"].type.python_type == Decimal


class TestAllModelsHaveTimestamps:
    """Test that all models have proper timestamp fields."""

    @pytest.mark.parametrize(
        "model",
        [User, Upload, UploadPipelineRun, MediaEvent, ProcessingStep, PromptTemplate],
    )
    def test_model_has_created_at(self, model: type) -> None:
        """All models have created_at timestamp."""
        mapper = inspect(model)
        columns = {c.key for c in mapper.columns}
        assert "created_at" in columns, f"{model.__name__} missing created_at"

    def test_cost_model_has_effective_from(self) -> None:
        """CostModel uses effective_from instead of created_at per PRD."""
        mapper = inspect(CostModel)
        columns = {c.key for c in mapper.columns}
        assert "effective_from" in columns, "CostModel missing effective_from"


class TestBaseMetadata:
    """Test that all models are registered with Base."""

    def test_all_models_in_base_metadata(self) -> None:
        """All models are registered in Base.metadata for Alembic."""
        table_names = set(Base.metadata.tables.keys())

        expected = {
            "users",
            "uploads",
            "upload_pipeline_runs",
            "media_events",
            "processing_steps",
            "prompt_templates",
            "cost_models",
        }
        assert expected.issubset(table_names), f"Missing tables: {expected - table_names}"
