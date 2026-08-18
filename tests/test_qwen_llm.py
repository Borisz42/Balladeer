import pytest
from app.models.qwen_llm import qwen_llm
from app.core.memory_manager import memory_manager

def test_qwen_llm_draft_travel_log():
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
    
    draft = qwen_llm.draft_travel_log(sample_media, project_title="Paris Trip")
    assert draft is not None
    assert "diary_days" in draft
    assert len(draft["diary_days"]) >= 1
    assert "narrative_text" in draft
    assert len(draft["narrative_text"]) > 10


def test_qwen_llm_generate_story_and_lyrics():
    acts = [
        {
            "act_type": "Verse 1",
            "day": 1,
            "title": "Day 1",
            "lines": ["Walking through morning streets", "Under the golden light"]
        }
    ]
    lyrics, prompt = qwen_llm.generate_story_and_lyrics(acts, narrative_text="Walking through Paris streets.", is_instrumental=False)
    assert len(lyrics) > 0
    assert len(prompt) > 0
