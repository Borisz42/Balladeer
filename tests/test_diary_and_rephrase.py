import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.database import db, ProjectModel, MediaAssetModel
from app.pipeline.rephraser import diary_rephraser
from app.pipeline.music_gen import MusicGenerator
from app.pipeline.indexer import indexer

client = TestClient(app)

def test_rephraser_spelling_and_grammar_correction():
    raw = "arived in kyoto amidst beatiful moring rain. walking to tempel wiht thier lanterns"
    fixed = diary_rephraser.fix_spelling_and_grammar(raw)
    assert "Arrived" in fixed
    assert "Kyoto" in fixed
    assert "beautiful" in fixed
    assert "morning" in fixed
    assert "temple" in fixed
    assert "with" in fixed
    assert "their" in fixed
    assert fixed.endswith(".")

def test_rephraser_single_day_and_structured_days():
    # Single day
    raw_day = "moring banboo forest walk under sunst."
    rephrased = diary_rephraser.rephrase_single_day(raw_day, day_number=2, date_str="2026-08-18")
    assert "morning" in rephrased.lower()
    assert "bamboo" in rephrased.lower()
    assert "sunset" in rephrased.lower()

    # Structured days
    days = [
        {"day_number": 1, "date": "2026-08-17", "events": "arived in tokyo wiht fast train", "is_active": True},
        {"day_number": 2, "date": "2026-08-18", "events": "shibuya neon lights midnigth", "is_active": True}
    ]
    rephrased_days = diary_rephraser.rephrase_structured_days(days)
    assert len(rephrased_days) == 2
    assert "Arrived" in rephrased_days[0]["events"]
    assert "Tokyo" in rephrased_days[0]["events"]
    assert "with" in rephrased_days[0]["events"]
    assert "Shibuya" in rephrased_days[1]["events"]
    assert "midnight" in rephrased_days[1]["events"]

def test_music_gen_partition_with_structured_and_discarded_days():
    music_gen = MusicGenerator()

    diary_days = [
        {"day_number": 1, "date": "2026-08-17", "title": "Day 1", "events": "Kyoto temple walk", "is_active": True, "is_discarded": False},
        {"day_number": 2, "date": "2026-08-18", "title": "Day 2", "events": "Rainy day rest", "is_active": False, "is_discarded": True},
        {"day_number": 3, "date": "2026-08-19", "title": "Day 3", "events": "Tokyo Shibuya crossing", "is_active": True, "is_discarded": False}
    ]

    acts = music_gen.partition_narrative_to_acts(diary_text="", diary_days=diary_days)
    
    # Should only contain active days (Day 1 and Day 3) plus Chorus and Outro
    verse_days = [a["day"] for a in acts if a["act_type"].startswith("Verse")]
    assert 1 in verse_days
    assert 3 in verse_days
    assert 2 not in verse_days # Discarded day must be omitted

def test_date_aware_media_indexing_sync():
    import os
    proj_id = f"proj_sync_{os.urandom(3).hex()}"
    db.create_project(ProjectModel(
        id=proj_id,
        title="Date Sync Test",
        narrative_text="Day 1: Arrival\nDay 2: Exploration"
    ))

    ast1_id = f"ast_1_{os.urandom(3).hex()}"
    ast2_id = f"ast_2_{os.urandom(3).hex()}"

    # Add mock assets with different capture times
    db.add_media_asset(MediaAssetModel(
        id=ast1_id,
        project_id=proj_id,
        file_path="mock1.jpg",
        media_type="image",
        capture_time="2026-08-17T10:00:00",
        tags=["nature"]
    ))
    db.add_media_asset(MediaAssetModel(
        id=ast2_id,
        project_id=proj_id,
        file_path="mock2.jpg",
        media_type="image",
        capture_time="2026-08-18T15:30:00",
        tags=["city"]
    ))

    diary_days = [
        {"day_number": 1, "date": "2026-08-17", "title": "Day 1 - Kyoto Arrival", "is_active": True},
        {"day_number": 2, "date": "2026-08-18", "title": "Day 2 - Bamboo Forest", "is_active": True}
    ]

    updated_count = indexer.sync_assets_with_diary_dates(proj_id, diary_days)
    assert updated_count == 2

    # Verify updated tags
    a1 = db.get_asset(ast1_id)
    assert "day:Day 1" in a1.tags
    assert "date:2026-08-17" in a1.tags

    a2 = db.get_asset(ast2_id)
    assert "day:Day 2" in a2.tags
    assert "date:2026-08-18" in a2.tags

def test_api_update_project_diary_and_rephrase():
    # 1. Create project
    create_res = client.post("/api/projects", json={
        "title": "Initial Title",
        "narrative_text": "Day 1: Old text"
    })
    assert create_res.status_code == 200
    p_id = create_res.json()["id"]

    # 2. Update diary endpoint
    update_res = client.put(f"/api/projects/{p_id}/diary", json={
        "title": "Updated Journey",
        "narrative_text": "Day 1 (2026-08-17): Arrived in Kyoto\nDay 2 (2026-08-18): Tokyo neon lights",
        "config_override": {
            "start_date": "2026-08-17",
            "finish_date": "2026-08-18",
            "diary_days": [
                {"day_number": 1, "date": "2026-08-17", "events": "Arrived in Kyoto", "is_active": True, "is_discarded": False},
                {"day_number": 2, "date": "2026-08-18", "events": "Tokyo neon lights", "is_active": True, "is_discarded": False}
            ]
        }
    })
    assert update_res.status_code == 200
    detail = update_res.json()
    assert detail["project"]["title"] == "Updated Journey"
    assert "diary_days" in detail["project"]["config_override"]

    # 3. AI Rephrase endpoint (single day)
    rephrase_res = client.post("/api/projects/rephrase", json={
        "text": "arived at kyoto tempel wiht beatiful lanterns",
        "day_number": 1,
        "date": "2026-08-17",
        "mode": "single_day"
    })
    assert rephrase_res.status_code == 200
    assert "Arrived" in rephrase_res.json()["rephrased_text"]
    assert "temple" in rephrase_res.json()["rephrased_text"]
    assert "beautiful" in rephrase_res.json()["rephrased_text"]

    # 4. AI Rephrase endpoint (structured days)
    rephrase_all_res = client.post(f"/api/projects/{p_id}/rephrase", json={
        "days": [
            {"day_number": 1, "date": "2026-08-17", "events": "arived at kyoto tempel", "is_active": True},
            {"day_number": 2, "date": "2026-08-18", "events": "shinkasen to tokyo midnigth", "is_active": True}
        ]
    })
    assert rephrase_all_res.status_code == 200
    res_data = rephrase_all_res.json()
    assert "rephrased_days" in res_data
    assert len(res_data["rephrased_days"]) == 2
    assert "Shinkansen" in res_data["rephrased_days"][1]["events"]
    assert "Tokyo" in res_data["rephrased_days"][1]["events"]
