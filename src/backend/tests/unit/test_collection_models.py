"""Tests for Collection and CollectionItem SQLAlchemy models."""

from app.models.collection import Collection, CollectionItem


class TestCollectionModel:
    def test_tablename(self):
        assert Collection.__tablename__ == "collections"

    def test_has_all_expected_columns(self):
        columns = {c.name for c in Collection.__table__.columns}
        expected = {
            "id",
            "user_id",
            "name",
            "description",
            "source_type",
            "conversation_id",
            "upload_id",
            "source_platform",
            "original_collection_id",
            "cover_image_url",
            "item_count",
            "metadata",
            "created_at",
            "updated_at",
        }
        assert expected == columns

    def test_user_id_not_nullable(self):
        col = Collection.__table__.c.user_id
        assert col.nullable is False

    def test_name_not_nullable(self):
        col = Collection.__table__.c.name
        assert col.nullable is False

    def test_source_type_default(self):
        col = Collection.__table__.c.source_type
        assert col.server_default is not None
        assert "manual" in str(col.server_default.arg)

    def test_item_count_default(self):
        col = Collection.__table__.c.item_count
        assert col.server_default is not None

    def test_conversation_id_nullable(self):
        col = Collection.__table__.c.conversation_id
        assert col.nullable is True

    def test_upload_id_nullable(self):
        col = Collection.__table__.c.upload_id
        assert col.nullable is True

    def test_unique_constraint_user_name(self):
        constraints = [
            c.name for c in Collection.__table__.constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_collections_user_name" in constraints

    def test_user_relationship_exists(self):
        rels = {r.key for r in Collection.__mapper__.relationships}
        assert "user" in rels

    def test_items_relationship_exists(self):
        rels = {r.key for r in Collection.__mapper__.relationships}
        assert "items" in rels

    def test_conversation_relationship_exists(self):
        rels = {r.key for r in Collection.__mapper__.relationships}
        assert "conversation" in rels

    def test_upload_relationship_exists(self):
        rels = {r.key for r in Collection.__mapper__.relationships}
        assert "upload" in rels

    def test_foreign_key_user_cascade_delete(self):
        fk = next(fk for fk in Collection.__table__.foreign_keys if "users" in fk.target_fullname)
        assert fk.ondelete == "CASCADE"

    def test_foreign_key_conversation_set_null(self):
        fk = next(
            fk for fk in Collection.__table__.foreign_keys if "conversations" in fk.target_fullname
        )
        assert fk.ondelete == "SET NULL"

    def test_foreign_key_upload_set_null(self):
        fk = next(fk for fk in Collection.__table__.foreign_keys if "uploads" in fk.target_fullname)
        assert fk.ondelete == "SET NULL"


class TestCollectionItemModel:
    def test_tablename(self):
        assert CollectionItem.__tablename__ == "collection_items"

    def test_has_all_expected_columns(self):
        columns = {c.name for c in CollectionItem.__table__.columns}
        expected = {
            "id",
            "collection_id",
            "media_event_id",
            "position",
            "added_at",
        }
        assert expected == columns

    def test_collection_id_not_nullable(self):
        col = CollectionItem.__table__.c.collection_id
        assert col.nullable is False

    def test_media_event_id_not_nullable(self):
        col = CollectionItem.__table__.c.media_event_id
        assert col.nullable is False

    def test_position_default(self):
        col = CollectionItem.__table__.c.position
        assert col.server_default is not None

    def test_unique_constraint_collection_media(self):
        constraints = [
            c.name for c in CollectionItem.__table__.constraints if hasattr(c, "name") and c.name
        ]
        assert "uq_collection_items_collection_media" in constraints

    def test_collection_relationship_exists(self):
        rels = {r.key for r in CollectionItem.__mapper__.relationships}
        assert "collection" in rels

    def test_media_event_relationship_exists(self):
        rels = {r.key for r in CollectionItem.__mapper__.relationships}
        assert "media_event" in rels

    def test_foreign_key_collection_cascade_delete(self):
        fk = next(
            fk
            for fk in CollectionItem.__table__.foreign_keys
            if "collections" in fk.target_fullname
        )
        assert fk.ondelete == "CASCADE"

    def test_foreign_key_media_event_cascade_delete(self):
        fk = next(
            fk
            for fk in CollectionItem.__table__.foreign_keys
            if "media_events" in fk.target_fullname
        )
        assert fk.ondelete == "CASCADE"


class TestUserCollectionsRelationship:
    def test_user_has_collections_relationship(self):
        from app.models.user import User

        rels = {r.key for r in User.__mapper__.relationships}
        assert "collections" in rels
