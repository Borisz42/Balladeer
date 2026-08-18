import pytest
from app.core.geocoder import reverse_geocode, format_location_context

def test_reverse_geocode_known_places():
    # Budapest, Hungary
    res_bp = reverse_geocode(47.51757, 19.04529)
    assert res_bp.get("country") == "Hungary"
    assert "Budapest" in res_bp.get("location_str", "")

    # Paris, France
    res_paris = reverse_geocode(48.87157, 2.3)
    assert res_paris.get("country") == "France"
    assert len(res_paris.get("location_str", "")) > 0

    # Rome, Italy
    res_rome = reverse_geocode(41.9028, 12.4964)
    assert res_rome.get("country") == "Italy"
    assert "Rome" in res_rome.get("location_str", "") or "Roma" in res_rome.get("location_str", "")


def test_format_location_context():
    meta = {
        "gps_lat": 47.51757,
        "gps_lon": 19.04529,
        "capture_time": "2023-05-26T07:13:38"
    }
    loc_str = format_location_context(meta)
    assert "Hungary" in loc_str
    assert "°" not in loc_str
