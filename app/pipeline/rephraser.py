import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Common typos and misspellings correction dictionary
COMMON_SPELLING_CORRECTIONS = {
    "teh": "the",
    "shoudl": "should",
    "woudl": "would",
    "coudl": "could",
    "taht": "that",
    "adn": "and",
    "nad": "and",
    "wiht": "with",
    "thier": "their",
    "recieve": "receive",
    "separete": "separate",
    "seperate": "separate",
    "moring": "morning",
    "morrning": "morning",
    "sunst": "sunset",
    "sunris": "sunrise",
    "beutiful": "beautiful",
    "beatiful": "beautiful",
    "wonderfull": "wonderful",
    "awsome": "awesome",
    "amzing": "amazing",
    "resturant": "restaurant",
    "restaraunt": "restaurant",
    "tempel": "temple",
    "moutain": "mountain",
    "mountian": "mountain",
    "visiting": "visiting",
    "explor": "explore",
    "explord": "explored",
    "traveled": "traveled",
    "travled": "traveled",
    "arived": "arrived",
    "arrivd": "arrived",
    "journly": "journey",
    "journy": "journey",
    "forrest": "forest",
    "bannboo": "bamboo",
    "banboo": "bamboo",
    "lanters": "lanterns",
    "lanter": "lantern",
    "shinkasen": "Shinkansen",
    "shinkansen": "Shinkansen",
    "kyoto": "Kyoto",
    "tokyo": "Tokyo",
    "osaka": "Osaka",
    "shibuya": "Shibuya",
    "gion": "Gion",
    "arashiyama": "Arashiyama",
    "alps": "Alps",
    "effiel": "Eiffel",
    "paris": "Paris",
    "venice": "Venice",
    "rome": "Rome",
    "midnigth": "midnight",
    "busteling": "bustling",
    "scenerys": "sceneries",
    "photograhy": "photography"
}

class DiaryRephraser:
    """
    AI & Heuristic NLP Engine for fixing spelling errors and re-phrasing travel diary text
    into evocative, beat-ready prose and musical narrative acts.
    """

    def fix_spelling_and_grammar(self, text: str) -> str:
        """Fixes common spelling mistakes, repeated words, and punctuation issues."""
        if not text or not text.strip():
            return text

        cleaned = text.strip()

        # Word boundary replace using dictionary
        def replace_word(match):
            word = match.group(0)
            lower_word = word.lower()
            if lower_word in COMMON_SPELLING_CORRECTIONS:
                replacement = COMMON_SPELLING_CORRECTIONS[lower_word]
                if word.isupper():
                    return replacement.upper()
                if word[0].isupper():
                    return replacement.capitalize()
                return replacement
            return word

        cleaned = re.sub(r"\b[a-zA-Z]+\b", replace_word, cleaned)

        # Fix duplicate words (e.g. "the the" -> "the")
        cleaned = re.sub(r"\b(\w+)\s+\1\b", r"\1", cleaned, flags=re.IGNORECASE)

        # Clean multiple spaces
        cleaned = re.sub(r"[ \t]+", " ", cleaned)

        # Ensure proper sentence capitalization
        sentences = re.split(r"([.!?]\s*)", cleaned)
        formatted_sentences = []
        for s in sentences:
            if s and s[0].islower() and not s.startswith("http"):
                s = s[0].upper() + s[1:]
            formatted_sentences.append(s)
        cleaned = "".join(formatted_sentences)

        # Ensure sentence ends with period if missing
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."

        return cleaned

    def polish_travel_prose(self, text: str) -> str:
        """
        Enhances descriptive narrative tone to create vibrant, cinematic journal sentences.
        """
        cleaned = self.fix_spelling_and_grammar(text)
        if not cleaned:
            return cleaned

        # Enhancements for short or fragmented notes
        words = cleaned.split()
        if len(words) <= 3 and not any(w in cleaned.lower() for w in ["arrived", "walked", "explored", "journey", "visited"]):
            # Turn concise notes into lyrical sentence
            return f"Explored {cleaned.rstrip('.')} under glowing skies."

        return cleaned

    def rephrase_single_day(
        self,
        day_text: str,
        day_number: Optional[int] = None,
        date_str: Optional[str] = None
    ) -> str:
        """
        Re-phrases and corrects spelling for a single day entry.
        """
        if not day_text or not day_text.strip():
            day_label = f"Day {day_number}" if day_number else "A new day"
            return f"{day_label}: Golden dawn illuminated scenic pathways and tranquil vistas."

        # Strip existing Day prefix if present for clean processing
        content = re.sub(r"^(?:Day\s*\d+|Stage\s*\d+|Act\s*\d+)(?:\s*\([^)]*\))?:\s*", "", day_text.strip(), flags=re.IGNORECASE)
        polished = self.polish_travel_prose(content)

        return polished

    def rephrase_full_diary(self, diary_text: str) -> str:
        """
        Re-phrases the full diary text line by line or day by day.
        """
        if not diary_text or not diary_text.strip():
            return ""

        lines = [l.strip() for l in diary_text.strip().split("\n") if l.strip()]
        rephrased_lines = []
        day_counter = 1

        for line in lines:
            day_match = re.match(r"^(?:Day\s*(\d+)|Stage\s*(\d+)|Act\s*(\d+))(?:\s*\(([^)]*)\))?:\s*(.*)$", line, re.IGNORECASE)
            if day_match:
                d_num = int(day_match.group(1) or day_match.group(2) or day_match.group(3) or day_counter)
                date_part = f" ({day_match.group(4)})" if day_match.group(4) else ""
                body = day_match.group(5)
                polished_body = self.rephrase_single_day(body, day_number=d_num)
                rephrased_lines.append(f"Day {d_num}{date_part}: {polished_body}")
                day_counter = d_num + 1
            else:
                polished = self.polish_travel_prose(line)
                rephrased_lines.append(f"Day {day_counter}: {polished}")
                day_counter += 1

        return "\n".join(rephrased_lines)

    def rephrase_structured_days(self, days: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Re-phrases each day in a structured day list.
        """
        rephrased = []
        for day in days:
            events = day.get("events", "")
            d_num = day.get("day_number", 1)
            date_str = day.get("date", "")
            polished_events = self.rephrase_single_day(events, day_number=d_num, date_str=date_str)

            rephrased.append({
                **day,
                "events": polished_events
            })
        return rephrased

diary_rephraser = DiaryRephraser()
