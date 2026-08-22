import pytest
from unittest.mock import MagicMock
from app.models.local_vlm import local_vlm
from app.core.memory_manager import memory_manager

def test_local_vlm_draft_travel_log():
    sample_media = [
        {
            "id": "ast_1",
            "caption": "Eiffel Tower under blue sky",
            "tags": ["eiffel", "tower", "paris", "travel"],
            "capture_time": "2023-05-26T10:00:00"
        },
        {
            "id": "ast_2",
            "caption": "Louvre museum glass pyramid",
            "tags": ["louvre", "museum", "paris"],
            "capture_time": "2023-05-26T15:00:00"
        }
    ]
    
    draft = local_vlm.draft_travel_log(sample_media, project_title="Paris Trip")
    assert draft is not None
    assert "diary_days" in draft
    assert len(draft["diary_days"]) >= 1
    assert "narrative_text" in draft
    assert len(draft["narrative_text"]) > 10


def test_local_vlm_generate_story_and_lyrics(monkeypatch):
    monkeypatch.setattr(local_vlm, "generate_text", lambda prompt, system_prompt="", max_tokens=280, **kwargs: "[Verse 1]\nWalking in Paris\n[Music Prompt]\nChilled French Pop with Accordion")
    acts = [
        {
            "act_type": "Verse 1",
            "day": 1,
            "title": "Day 1",
            "lines": ["Walking through morning streets", "Under the golden light"]
        }
    ]
    lyrics, prompt = local_vlm.generate_story_and_lyrics(acts, narrative_text="Walking through Paris streets.", is_instrumental=False)
    assert len(lyrics) > 0
    assert "Walking in Paris" in lyrics
    assert "French Pop" in prompt
