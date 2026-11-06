"""Unit tests for the source-packet helpers and the plan/contract split (no network, no DB)."""

import os

os.environ.setdefault("DB_NAME", "test_db")
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017")

from lib import producer, source_packet  # noqa: E402
from lib.producer_plan import DEFAULT_PLAN, OUTPUT_CONTRACT  # noqa: E402

PACKET = [
    {"id": "S1", "url": "https://wvpublic.org/a", "title": "A", "outlet": "wvpublic.org", "published": "2026-11-03",
     "text": "Comments accepted through Nov. 20.", "fetched": True, "grounded": True},
    {"id": "S2", "url": "https://example.com/b", "title": "B", "outlet": "example.com", "published": "",
     "text": "", "fetched": False, "grounded": True},
]


def test_parse_ids_accepts_common_shapes():
    assert source_packet.parse_ids(["S1", "S2"]) == ["S1", "S2"]
    assert source_packet.parse_ids([{"id": "S3"}]) == ["S3"]
    assert source_packet.parse_ids("S1, S4") == ["S1", "S4"]
    assert source_packet.parse_ids(None) == []


def test_to_links_only_returns_known_ids_and_never_invents_urls():
    links = source_packet.to_links(PACKET, ["S1", "S9", "S1", "[S2]"])
    assert [l["url"] for l in links] == ["https://wvpublic.org/a", "https://example.com/b"]
    assert all(l["grounded"] for l in links)


def test_render_includes_published_date_and_flags_missing_text():
    out = source_packet.render_for_prompt(PACKET)
    assert "published: 2026-11-03" in out and "Comments accepted through Nov. 20." in out
    assert "could not be retrieved" in out
    assert "no source articles" in source_packet.render_for_prompt([])


def test_text_and_date_extraction():
    html = ('<html><head><title>T</title><meta property="article:published_time" content="2026-11-05T10:00:00Z">'
            "<script>var x=1</script></head><body><nav>menu</nav><p>Hello &amp; welcome</p></body></html>")
    assert source_packet._published(html) == "2026-11-05"
    assert source_packet._clean_text(html) == "T Hello & welcome"


def test_urls_in_text_strips_trailing_punctuation():
    assert source_packet.urls_in_text("see https://a.com/x. and (https://b.com/y)") == ["https://a.com/x", "https://b.com/y"]


def test_system_prompt_keeps_locked_mechanics_even_with_custom_plan():
    system = producer.build_system("My custom plan " * 20)
    assert producer.REQUIRED_INTRO in system
    assert "On a Positive Note" in system and "source_ids" in system
    assert "My custom plan" in system
    assert "__REQUIRED_INTRO__" not in system


def test_contract_split_separates_mechanics_from_schema():
    mech, schema = producer._split_contract()
    assert "CHAPTER HEADERS" in mech and "DATES" in mech
    assert schema.startswith("OUTPUT:") and "recording_script" in schema
    assert "OUTPUT:" not in mech


def test_default_plan_is_editorial_only():
    assert "K-12 PRIORITY" in DEFAULT_PLAN and "VERIFICATION" in DEFAULT_PLAN
    assert "JSON" not in DEFAULT_PLAN and "## Introduction" not in DEFAULT_PLAN
    assert "source_ids" in OUTPUT_CONTRACT
