import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PMOVES_ROOT = Path(__file__).resolve().parents[3]
for candidate in (ROOT, PMOVES_ROOT):
    candidate_str = str(candidate)
    if candidate_str not in sys.path:
        sys.path.insert(0, candidate_str)

from pmoves.services.publisher import publisher


def test_slugify_and_output_path(tmp_path):
    base = tmp_path / "library"
    slug = publisher.slugify("Summer Gala 2024!!")
    out_path = publisher.derive_output_path(str(base), "Creative Works", slug, ".png")
    expected_dir = base / "creative-works"
    assert Path(out_path).parent == expected_dir
    assert Path(out_path).name == "creative-works--summer-gala-2024.png"
    assert expected_dir.exists()


def test_build_published_payload_merges_metadata():
    payload = publisher.build_published_payload(
        artifact_uri="s3://bucket/key",
        published_path="/library/creative-works/summer-gala-2024.png",
        namespace="Creative Works",
        title="Summer Gala 2024",
        description="A highlight reel",
        tags=["events", "summer"],
        incoming_meta={"title": "Custom Title", "camera": "FX3"},
        public_url="http://media.local/creative-works/summer-gala-2024.png",
        jellyfin_item_id="abc123",
        slug="summer-gala-2024",
        namespace_slug="creative-works",
        filename="creative-works--summer-gala-2024.png",
        extension=".png",
    )

    assert payload["artifact_uri"] == "s3://bucket/key"
    assert payload["published_path"].endswith("summer-gala-2024.png")
    assert payload["namespace"] == "Creative Works"
    assert payload["public_url"].endswith("summer-gala-2024.png")
    assert payload["jellyfin_item_id"] == "abc123"

    meta = payload["meta"]
    assert meta["title"] == "Custom Title"
    assert meta["description"] == "A highlight reel"
    assert meta["tags"] == ["events", "summer"]
    assert meta["camera"] == "FX3"
    assert meta["slug"] == "summer-gala-2024"
    assert meta["namespace_slug"] == "creative-works"
    assert meta["filename"] == "creative-works--summer-gala-2024.png"
    assert meta["extension"] == "png"


def test_merge_metadata_preserves_existing_slug_and_namespace():
    meta = publisher.merge_metadata(
        "Test",
        None,
        None,
        {"slug": "custom", "namespace_slug": "custom-ns"},
        slug="generated",
        namespace_slug="generated-ns",
        filename="generated-ns--generated.png",
        extension=".png",
    )

    assert meta["slug"] == "custom"
    assert meta["namespace_slug"] == "custom-ns"
    assert meta["filename"] == "generated-ns--generated.png"
    assert meta["extension"] == "png"
