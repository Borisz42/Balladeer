import re
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.database.database import db
from app.database.models import ProjectModel, MediaAssetModel
from app.pipeline.music_gen import music_gen

client = TestClient(app)

def test_music_generator_timeline_estimate():
    proj_id = "test_music_est_proj"
    
    # Create test assets
    assets = [
        MediaAssetModel(
            id="asset_1",
            project_id=proj_id,
            file_path="sample_media/portrait_day1.jpg",
            media_type="image",
            quality_score=9.0,
            relevance_score_daily=0.85,
            is_active=True,
            tags=["day:Day 1"]
        ),
        MediaAssetModel(
            id="asset_2",
            project_id=proj_id,
            file_path="sample_media/landscape_day3.jpg",
            media_type="image",
            quality_score=6.0,
            relevance_score_daily=0.3,
            is_active=True,
            tags=["day:Day 1"]
        ),
        MediaAssetModel(
            id="asset_3",
            project_id=proj_id,
            file_path="sample_media/video_day2.mp4",
            media_type="video",
            duration_sec=8.0,
            quality_score=8.5,
            relevance_score_daily=0.9,
            is_active=True,
            tags=["day:Day 2"]
        )
    ]
    
    diary_days = [
        {"day_number": 1, "title": "Paris Morning", "events": "Walking by the Seine", "is_active": True},
        {"day_number": 2, "title": "Rome Adventure", "events": "Colosseum and sunset", "is_active": True}
    ]
    
    custom_cfg = {
        "pacing_rules": {"pacing_preset": "fast", "photo_sec": 1.5, "video_sec_max": 3.0},
        "default_inclusion_threshold": 50.0,
        "daily_inclusion_thresholds": {"1": 50.0, "2": 100.0}
    }
    
    res = music_gen.calculate_media_timeline_estimate(
        project_id=proj_id,
        diary_days=diary_days,
        assets=assets,
        custom_config=custom_cfg
    )
    
    assert res is not None
    assert "total_duration_sec" in res
    assert res["total_duration_sec"] > 0
    assert "daily_stats" in res
    assert len(res["daily_stats"]) == 2
    
    # Day 1 has 2 items, top 50% includes 1 item
    d1 = res["daily_stats"][0]
    assert d1["day_number"] == 1
    assert d1["total_media_count"] == 2
    assert d1["included_media_count"] == 1
    assert "asset_1" in d1["included_asset_ids"]
    assert "asset_2" in d1["excluded_asset_ids"]
    
    # Day 2 has 1 item, top 100% includes 1 item
    d2 = res["daily_stats"][1]
    assert d2["day_number"] == 2
    assert d2["total_media_count"] == 1
    assert d2["included_media_count"] == 1
    assert "asset_3" in d2["included_asset_ids"]
    
    # Acts should contain Intro, Verse 1, Chorus, Verse 2, Outro
    acts = res["acts"]
    assert len(acts) >= 4
    act_types = [a["act_type"] for a in acts]
    assert "Intro" in act_types
    assert "Verse 1" in act_types
    assert "Chorus" in act_types
    assert "Verse 2" in act_types
    assert "Outro" in act_types

def test_music_studio_api_endpoints():
    # 1. Create project
    create_resp = client.post("/api/projects", json={
        "title": "Music Studio Test Project",
        "narrative_text": "Day 1 (2026-06-01): Walking through Paris\nDay 2 (2026-06-02): Exploring Rome",
        "config_override": {
            "diary_days": [
                {"day_number": 1, "title": "Paris", "events": "Seine river walk", "date": "2026-06-01", "is_active": True},
                {"day_number": 2, "title": "Rome", "events": "Colosseum exploration", "date": "2026-06-02", "is_active": True}
            ]
        }
    })
    assert create_resp.status_code == 200
    proj_data = create_resp.json()
    proj_id = proj_data["id"]

    # 2. Add assets to DB
    asset_1 = MediaAssetModel(
        id=f"a1_{proj_id}",
        project_id=proj_id,
        file_path="sample_media/portrait_day1.jpg",
        media_type="image",
        quality_score=8.5,
        relevance_score_daily=0.8,
        tags=["day:Day 1"]
    )
    asset_2 = MediaAssetModel(
        id=f"a2_{proj_id}",
        project_id=proj_id,
        file_path="sample_media/landscape_day3.jpg",
        media_type="image",
        quality_score=5.0,
        relevance_score_daily=0.2,
        tags=["day:Day 1"]
    )
    db.add_media_asset(asset_1)
    db.add_media_asset(asset_2)

    # 3. Test analyze timeline endpoint
    analyze_resp = client.post(f"/api/projects/{proj_id}/music/analyze-timeline", json={
        "pacing_preset": "balanced",
        "default_inclusion_threshold": 60.0
    })
    assert analyze_resp.status_code == 200
    an_data = analyze_resp.json()
    assert "total_duration_sec" in an_data
    assert "daily_stats" in an_data
    assert len(an_data["daily_stats"]) == 2

    # 4. Test toggle inclusion endpoint
    # Toggle exclude asset_1 with threshold 7.0
    toggle_resp = client.post(f"/api/projects/{proj_id}/assets/{asset_1.id}/toggle-inclusion", json={
        "include": False,
        "threshold_score": 7.0,
        "delta": 0.2
    })
    assert toggle_resp.status_code == 200
    t_data = toggle_resp.json()
    assert t_data["status"] == "updated"
    assert t_data["new_score"] < 7.0

    # Toggle include asset_2 with threshold 7.0
    toggle_inc = client.post(f"/api/projects/{proj_id}/assets/{asset_2.id}/toggle-inclusion", json={
        "include": True,
        "threshold_score": 7.0,
        "delta": 0.2
    })
    assert toggle_inc.status_code == 200
    t_inc_data = toggle_inc.json()
    assert t_inc_data["status"] == "updated"
    assert t_inc_data["new_score"] >= 7.0

    # 5. Test generate-prompt endpoint
    p_resp = client.post(f"/api/projects/{proj_id}/music/generate-prompt", json={
        "style_vibe": "Acoustic Indie Folk Pop",
        "suggested_bpm": 118,
        "total_duration_sec": 35.0,
        "acts": an_data["acts"]
    })
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert "flow_prompt" in p_data
    assert len(p_data["flow_prompt"]) > 10

    # 6. Test generate-lyrics endpoint
    l_resp = client.post(f"/api/projects/{proj_id}/music/generate-lyrics", json={
        "flow_prompt": p_data["flow_prompt"],
        "is_instrumental": False,
        "acts": an_data["acts"]
    })
    assert l_resp.status_code == 200
    l_data = l_resp.json()
    assert "lyrics" in l_data
    assert len(l_data["lyrics"]) > 10
    # First tag must be [0:00-
    assert l_data["lyrics"].startswith("[0:00-")

def test_enforce_acts_timeline_18s_exact():
    acts_18s = [
        {"act_type": "Intro", "title": "Intro", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0, "is_instrumental": True, "directions": "Soft acoustic strumming"},
        {"act_type": "Verse 1", "title": "Paris Walk", "start_sec": 4.0, "end_sec": 14.0, "duration_sec": 10.0, "is_instrumental": False, "lines": ["Strolling down the Parisian street", "Morning sun so warm and sweet"]},
        {"act_type": "Outro", "title": "Outro", "start_sec": 14.0, "end_sec": 18.0, "duration_sec": 4.0, "is_instrumental": True, "directions": "Fading harmony"}
    ]

    # Test with hallucinated 45s raw LLM output
    hallucinated_45s_output = (
        "[0:00-0:10] [Intro]\n"
        "[0:10-0:25] [Verse 1]\n"
        "Walking through Paris all day long\n"
        "Singing a brand new summer song\n\n"
        "[0:25-0:35] [Chorus]\n"
        "Every moment shines so bright\n\n"
        "[0:35-0:45] [Verse 2]\n"
        "Sun goes down in the " # Cut off!
    )

    clean_lyrics = music_gen.enforce_acts_timeline_on_lyrics(acts_18s, hallucinated_45s_output)
    
    assert "[0:00-0:04] [Intro] (4s)" in clean_lyrics
    assert "[0:04-0:14] [Verse 1: Paris Walk] (10s)" in clean_lyrics
    assert "[0:14-0:18] [Outro] (4s)" in clean_lyrics
    assert "0:45" not in clean_lyrics
    assert "0:35" not in clean_lyrics
    assert clean_lyrics.endswith("[Instrumental - Fading harmony]")

def test_enforce_acts_timeline_rejects_header_echo():
    acts = [
        {"act_type": "Intro", "title": "Acoustic Intro", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0, "is_instrumental": True},
        {"act_type": "Verse 1", "title": "Person & Holds & White", "start_sec": 4.0, "end_sec": 28.0, "duration_sec": 24.0, "is_instrumental": False, "lines": []},
        {"act_type": "Outro", "title": "Acoustic Outro", "start_sec": 28.0, "end_sec": 32.0, "duration_sec": 4.0, "is_instrumental": True}
    ]
    raw_bad_output = (
        "[0:00-0:04] [Intro: Acoustic Intro Swell] (4s)\n"
        "[Instrumental - Atmospheric acoustic guitar swell.]\n\n"
        "[0:04-0:28] [Verse 1: Person & Holds & White] (24s)\n"
        "**Verse 1: Person & Holds & White**\n\n"
        "[0:28-0:32] [Outro: Acoustic Outro Fade] (4s)\n"
        "[Instrumental - Acoustic guitar fade-out.]"
    )
    res = music_gen.enforce_acts_timeline_on_lyrics(acts, raw_bad_output)
    assert "**" not in res
    assert "Verse 1: Person & Holds & White**" not in res
    assert "Person & Holds & White" not in res
    # Should contain real sung poetic lines
    assert len(res.split("\n")) >= 6

def test_enforce_acts_timeline_instrumental_spoken_subtitles():
    acts = [
        {"act_type": "Intro", "title": "Intro", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0},
        {"act_type": "Verse 1", "title": "Paris Journey", "start_sec": 4.0, "end_sec": 16.0, "duration_sec": 12.0},
        {"act_type": "Outro", "title": "Outro", "start_sec": 16.0, "end_sec": 20.0, "duration_sec": 4.0}
    ]

    # Test instrumental fallback story narration
    clean_subs = music_gen.enforce_acts_timeline_on_lyrics(acts, "", is_instrumental=True)
    assert "[0:00-0:04] [Intro] (4s)" in clean_subs
    assert "[0:04-0:16] [Verse 1: Paris Journey] (12s)" in clean_subs
    assert "[0:16-0:20] [Outro] (4s)" in clean_subs
    
    # Must NOT be an empty [Instrumental - ...] tag, but real spoken story narration
    assert "journey" in clean_subs.lower() or "walking" in clean_subs.lower() or "exploring" in clean_subs.lower()
    
    # Word count in the 12s verse should be normal speaking pace (~20-30 words)
    verse_text = clean_subs.split("[0:04-0:16] [Verse 1: Paris Journey] (12s)\n")[1].split("\n\n")[0]
    words = verse_text.split()
    assert 15 <= len(words) <= 35

def test_enforce_acts_timeline_no_sentence_cutoffs():
    acts = [
        {"act_type": "Intro", "title": "Acoustic Intro Swell", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0},
        {"act_type": "Verse 1", "title": "Day 1", "start_sec": 4.0, "end_sec": 21.0, "duration_sec": 17.0},
        {"act_type": "Outro", "title": "Acoustic Outro Fade", "start_sec": 21.0, "end_sec": 26.0, "duration_sec": 5.0}
    ]

    # Simulating the raw LLM output with long run-on sentences that were previously cut off
    raw_with_runons = (
        "[0:00-0:04] [Intro: Acoustic Intro Swell] (4s)\n"
        "The sun rises over the sleepy town, casting a warm golden glow across the quiet streets.\n\n"
        "[0:04-0:21] [Verse 1: Day 1] (17s)\n"
        "We begin our journey at Le Pré-Saint-Gervais station, where a person holds a white card with text and a QR code near a metal detector. "
        "The scene is bustling with activity, capturing the essence of daily life in this charming French town.\n\n"
        "[0:21-0:26] [Outro: Acoustic Outro Fade] (5s)\n"
        "As the day unfolds, we find ourselves amidst the picturesque landscape and peaceful atmosphere."
    )

    clean_subs = music_gen.enforce_acts_timeline_on_lyrics(acts, raw_with_runons, is_instrumental=True)
    
    # Must NOT contain cutoffs like 'casting a.' or 'amidst the picturesque.'
    assert "casting a." not in clean_subs
    assert "the picturesque." not in clean_subs
    assert not re.search(r"\b(a|an|the|of|to|in|on|with|and|as|casting|amidst)\.\s*$", clean_subs, re.MULTILINE)
    
    # Intro must be a complete sentence
    intro_block = clean_subs.split("\n\n")[0]
    assert intro_block.endswith(".")
    # Intro line must be grammatically complete
    intro_text = intro_block.split("\n")[1]
    assert intro_text in {
        "The sun rises over the sleepy town.",
        "Our journey begins as morning light breaks across the horizon."
    } or len(intro_text.split()) >= 6

def test_enforce_acts_timeline_rejects_raw_caption_and_enforces_rhyme():
    acts = [
        {"act_type": "Intro", "title": "Acoustic Intro Swell", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0, "is_instrumental": True},
        {"act_type": "Verse 1", "title": "Day 1", "start_sec": 4.0, "end_sec": 21.0, "duration_sec": 17.0, "is_instrumental": False},
        {"act_type": "Outro", "title": "Acoustic Outro Fade", "start_sec": 21.0, "end_sec": 26.0, "duration_sec": 5.0, "is_instrumental": True}
    ]

    # Simulating raw output containing a technical camera/OCR caption
    raw_with_ocr = (
        "[0:00-0:04] [Intro: Acoustic Intro Swell] (4s)\n"
        "[Instrumental - Atmospheric acoustic guitar swell.]\n\n"
        "[0:04-0:21] [Verse 1: Day 1] (17s)\n"
        "In the morning's gentle swell, our hearts align,\n"
        "A person holds a white card with text and a qr code near a metal detector at the entrance to Le Pré-Saint-Gervais station.\n\n"
        "[0:21-0:26] [Outro: Acoustic Outro Fade] (5s)\n"
        "[Instrumental - Acoustic guitar fade-out.]"
    )

    clean_lyrics = music_gen.enforce_acts_timeline_on_lyrics(acts, raw_with_ocr, is_instrumental=False)

    # Must NOT contain the raw technical OCR phrase
    assert "qr code" not in clean_lyrics.lower()
    assert "white card" not in clean_lyrics.lower()
    assert "metal detector" not in clean_lyrics.lower()

    # Must contain valid rhyming lines for Verse 1 (17s requires 4 lines)
    verse_block = clean_lyrics.split("[0:04-0:21] [Verse 1: Day 1] (17s)\n")[1].split("\n\n")[0]
    lines = [l.strip() for l in verse_block.split("\n") if l.strip()]
    assert len(lines) == 4
    for l in lines:
        assert len(l.split()) >= 4
        assert len(l.split()) <= 16

def test_enforce_acts_timeline_instrumental_expands_short_sentences():
    acts = [
        {"act_type": "Intro", "title": "Intro Swell", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0},
        {"act_type": "Verse 1", "title": "Day 1", "start_sec": 4.0, "end_sec": 22.0, "duration_sec": 18.0},
        {"act_type": "Outro", "title": "Outro Fade", "start_sec": 22.0, "end_sec": 26.0, "duration_sec": 4.0}
    ]

    # Simulating LLM returning only 1 brief 10-word sentence for an 18s section
    raw_brief = (
        "[0:00-0:04] [Intro: Intro Swell] (4s)\n"
        "Our journey begins as morning light breaks across the horizon.\n\n"
        "[0:04-0:22] [Verse 1: Day 1] (18s)\n"
        "As the sun sets, we hold onto memories from an unforgettable day.\n\n"
        "[0:22-0:26] [Outro: Outro Fade] (4s)\n"
        "As the day comes to a close, we hold onto memories."
    )

    clean_subs = music_gen.enforce_acts_timeline_on_lyrics(acts, raw_brief, is_instrumental=True)
    verse_block = clean_subs.split("[0:04-0:22] [Verse 1: Day 1] (18s)\n")[1].split("\n\n")[0]
    words = verse_block.split()
    # 18s spoken narration must be between 25 and 55 words (2-3 complete sentences)
    assert len(words) >= 25
    assert len(words) <= 55
    assert verse_block.endswith(".")

def test_enforce_acts_timeline_checks_rhyme_and_rejects_identical_endwords():
    acts = [
        {"act_type": "Intro", "title": "Acoustic Intro Swell", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0, "is_instrumental": True},
        {"act_type": "Verse 1", "title": "Day 1", "start_sec": 4.0, "end_sec": 21.0, "duration_sec": 17.0, "is_instrumental": False},
        {"act_type": "Outro", "title": "Acoustic Outro Fade", "start_sec": 21.0, "end_sec": 26.0, "duration_sec": 5.0, "is_instrumental": True}
    ]

    # Simulating LLM repeating the same word 'meet' / 'meet' or non-rhyming pairs
    raw_bad_rhyme = (
        "[0:00-0:04] [Intro: Acoustic Intro Swell] (4s)\n"
        "[Instrumental - Acoustic guitar build]\n\n"
        "[0:04-0:21] [Verse 1: Day 1] (17s)\n"
        "In the morning light we take a stroll\n"
        "A destination that frees the soul\n"
        "A path unfolds where cobblestones meet\n"
        "Underneath the blue sky where memories meet\n\n"
        "[0:21-0:26] [Outro: Acoustic Outro Fade] (5s)\n"
        "[Instrumental - Acoustic guitar fade-out]"
    )

    clean_lyrics = music_gen.enforce_acts_timeline_on_lyrics(acts, raw_bad_rhyme, is_instrumental=False)
    verse_block = clean_lyrics.split("[0:04-0:21] [Verse 1: Day 1] (17s)\n")[1].split("\n\n")[0]
    lines = [l.strip() for l in verse_block.split("\n") if l.strip()]
    assert len(lines) == 4
    # The repeated 'meet' / 'meet' line pair must be fixed so line 3 and line 4 end in distinct rhyming words
    last_word_3 = lines[2].split()[-1].lower().rstrip(".,;:!?")
    last_word_4 = lines[3].split()[-1].lower().rstrip(".,;:!?")
    assert last_word_3 != last_word_4

def test_enforce_acts_timeline_instrumental_subtitle_line_breaks():
    acts = [
        {"act_type": "Intro", "title": "Intro", "start_sec": 0.0, "end_sec": 4.0, "duration_sec": 4.0},
        {"act_type": "Verse 1", "title": "Day 1", "start_sec": 4.0, "end_sec": 22.0, "duration_sec": 18.0},
        {"act_type": "Outro", "title": "Outro", "start_sec": 22.0, "end_sec": 26.0, "duration_sec": 4.0}
    ]

    clean_subs = music_gen.enforce_acts_timeline_on_lyrics(acts, "", is_instrumental=True)
    verse_block = clean_subs.split("[0:04-0:22] [Verse 1: Day 1] (18s)\n")[1].split("\n\n")[0]
    # Subtitles must be broken into readable lines, each <= 16 words
    sub_lines = [l for l in verse_block.split("\n") if l.strip()]
    assert len(sub_lines) >= 2
    for l in sub_lines:
        assert len(l.split()) <= 16




