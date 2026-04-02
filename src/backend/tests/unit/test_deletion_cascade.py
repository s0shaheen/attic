"""Verify deletion cascades through all user-owned tables.

These tests verify that the ORM-level cascade configuration is correct
by checking that all user-owned models have cascade="all, delete" on
their parent relationship, and that the FK-level ondelete="CASCADE" is
set as a safety net.
"""

from uuid import UUID

import pytest
from sqlalchemy import inspect

from app.models.collection import Collection, CollectionItem
from app.models.conversation import Conversation, Message
from app.models.media_event import MediaEvent
from app.models.processing_step import ProcessingStep
from app.models.upload import Upload
from app.models.upload_pipeline_run import UploadPipelineRun
from app.models.user import User


def _get_relationship(model, attr_name):
    """Get a SQLAlchemy relationship property from a model."""
    mapper = inspect(model)
    return mapper.relationships[attr_name]


def _get_fk_ondelete(model, column_name: str) -> str | None:
    """Get the ondelete action for a FK column."""
    mapper = inspect(model)
    col = mapper.columns[column_name]
    for fk in col.foreign_keys:
        return fk.ondelete
    return None


class TestUserCascadeRelationships:
    """Verify User model has cascade='all, delete' on all child relationships."""

    def test_user_uploads_cascade(self):
        rel = _get_relationship(User, "uploads")
        assert "delete" in rel.cascade

    def test_user_pipeline_runs_cascade(self):
        rel = _get_relationship(User, "pipeline_runs")
        assert "delete" in rel.cascade

    def test_user_media_events_cascade(self):
        rel = _get_relationship(User, "media_events")
        assert "delete" in rel.cascade

    def test_user_collections_cascade(self):
        rel = _get_relationship(User, "collections")
        assert "delete" in rel.cascade

    def test_user_conversations_cascade(self):
        rel = _get_relationship(User, "conversations")
        assert "delete" in rel.cascade


class TestUploadCascadeRelationships:
    """Verify Upload model cascades to pipeline_runs and media_events."""

    def test_upload_pipeline_runs_cascade(self):
        rel = _get_relationship(Upload, "pipeline_runs")
        assert "delete" in rel.cascade

    def test_upload_media_events_cascade(self):
        rel = _get_relationship(Upload, "media_events")
        assert "delete" in rel.cascade


class TestMediaEventCascadeRelationships:
    """Verify MediaEvent cascades to processing_steps."""

    def test_media_event_processing_steps_cascade(self):
        rel = _get_relationship(MediaEvent, "processing_steps")
        assert "delete" in rel.cascade


class TestCollectionCascadeRelationships:
    """Verify Collection cascades to collection_items."""

    def test_collection_items_cascade(self):
        rel = _get_relationship(Collection, "items")
        assert "delete" in rel.cascade


class TestConversationCascadeRelationships:
    """Verify Conversation cascades to messages."""

    def test_conversation_messages_cascade(self):
        rel = _get_relationship(Conversation, "messages")
        assert "delete" in rel.cascade


class TestForeignKeyCascade:
    """Verify DB-level ondelete='CASCADE' on all user-owned FKs."""

    def test_upload_user_fk(self):
        assert _get_fk_ondelete(Upload, "user_id") == "CASCADE"

    def test_media_event_user_fk(self):
        assert _get_fk_ondelete(MediaEvent, "user_id") == "CASCADE"

    def test_collection_user_fk(self):
        assert _get_fk_ondelete(Collection, "user_id") == "CASCADE"

    def test_conversation_user_fk(self):
        assert _get_fk_ondelete(Conversation, "user_id") == "CASCADE"

    def test_pipeline_run_upload_fk(self):
        assert _get_fk_ondelete(UploadPipelineRun, "upload_id") == "CASCADE"

    def test_media_event_upload_fk(self):
        assert _get_fk_ondelete(MediaEvent, "upload_id") == "CASCADE"

    def test_collection_item_collection_fk(self):
        assert _get_fk_ondelete(CollectionItem, "collection_id") == "CASCADE"

    def test_collection_item_media_event_fk(self):
        assert _get_fk_ondelete(CollectionItem, "media_event_id") == "CASCADE"

    def test_message_conversation_fk(self):
        assert _get_fk_ondelete(Message, "conversation_id") == "CASCADE"

    def test_processing_step_media_event_fk(self):
        assert _get_fk_ondelete(ProcessingStep, "media_event_id") == "CASCADE"


class TestFullCascadeChain:
    """Verify the complete cascade chain from User → leaves."""

    def test_all_user_owned_tables_have_cascade(self):
        """Every direct child of User must have cascade='all, delete'."""
        user_rels = inspect(User).relationships
        child_relationships = {
            "uploads",
            "pipeline_runs",
            "media_events",
            "collections",
            "conversations",
        }
        for name in child_relationships:
            rel = user_rels[name]
            assert "delete" in rel.cascade, (
                f"User.{name} missing 'delete' cascade — "
                f"deleting a user will not cascade to {rel.mapper.class_.__tablename__}"
            )

    def test_no_orphan_tables_without_cascade(self):
        """Verify all leaf models that reference User (directly or transitively)
        are in the cascade chain."""
        # These are all tables that hold user data and must be cleaned up
        expected_cascaded = {
            "uploads",          # User → Upload
            "upload_pipeline_runs",  # User → UploadPipelineRun, Upload → UploadPipelineRun
            "media_events",     # User → MediaEvent, Upload → MediaEvent
            "processing_steps", # MediaEvent → ProcessingStep
            "collections",      # User → Collection
            "collection_items", # Collection → CollectionItem
            "conversations",    # User → Conversation
            "messages",         # Conversation → Message
        }

        # Verify each table is reachable via cascade from User
        user_mapper = inspect(User)
        reachable = set()

        def _walk(mapper, depth=0):
            if depth > 5:
                return
            for rel in mapper.relationships:
                if "delete" in rel.cascade:
                    target_table = rel.mapper.class_.__tablename__
                    reachable.add(target_table)
                    _walk(inspect(rel.mapper.class_), depth + 1)

        _walk(user_mapper)

        missing = expected_cascaded - reachable
        assert not missing, (
            f"Tables not reachable via ORM cascade from User: {missing}. "
            "These tables will be orphaned when a user is deleted."
        )
