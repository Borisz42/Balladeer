import logging
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger("balladeer.geocoder")

# Comprehensive ISO 3166-1 alpha-2 country mapping
COUNTRY_MAP = {
    "AD": "Andorra", "AE": "United Arab Emirates", "AF": "Afghanistan", "AG": "Antigua and Barbuda",
    "AL": "Albania", "AM": "Armenia", "AO": "Angola", "AR": "Argentina", "AT": "Austria",
    "AU": "Australia", "AZ": "Azerbaijan", "BA": "Bosnia and Herzegovina", "BB": "Barbados",
    "BD": "Bangladesh", "BE": "Belgium", "BF": "Burkina Faso", "BG": "Bulgaria", "BH": "Bahrain",
    "BI": "Burundi", "BJ": "Benin", "BN": "Brunei", "BO": "Bolivia", "BR": "Brazil", "BS": "Bahamas",
    "BT": "Bhutan", "BW": "Botswana", "BY": "Belarus", "BZ": "Belize", "CA": "Canada",
    "CD": "Democratic Republic of the Congo", "CF": "Central African Republic", "CG": "Congo",
    "CH": "Switzerland", "CI": "Ivory Coast", "CL": "Chile", "CM": "Cameroon", "CN": "China",
    "CO": "Colombia", "CR": "Costa Rica", "CU": "Cuba", "CV": "Cape Verde", "CY": "Cyprus",
    "CZ": "Czech Republic", "DE": "Germany", "DJ": "Djibouti", "DK": "Denmark", "DM": "Dominica",
    "DO": "Dominican Republic", "DZ": "Algeria", "EC": "Ecuador", "EE": "Estonia", "EG": "Egypt",
    "ES": "Spain", "ET": "Ethiopia", "FI": "Finland", "FJ": "Fiji", "FR": "France", "GA": "Gabon",
    "GB": "United Kingdom", "GD": "Grenada", "GE": "Georgia", "GH": "Ghana", "GM": "Gambia",
    "GN": "Guinea", "GR": "Greece", "GT": "Guatemala", "GW": "Guinea-Bissau", "GY": "Guyana",
    "HK": "Hong Kong", "HN": "Honduras", "HR": "Croatia", "HT": "Haiti", "HU": "Hungary",
    "ID": "Indonesia", "IE": "Ireland", "IL": "Israel", "IN": "India", "IQ": "Iraq", "IR": "Iran",
    "IS": "Iceland", "IT": "Italy", "JM": "Jamaica", "JO": "Jordan", "JP": "Japan", "KE": "Kenya",
    "KG": "Kyrgyzstan", "KH": "Cambodia", "KR": "South Korea", "KW": "Kuwait", "KZ": "Kazakhstan",
    "LA": "Laos", "LB": "Lebanon", "LI": "Liechtenstein", "LK": "Sri Lanka", "LT": "Lithuania",
    "LU": "Luxembourg", "LV": "Latvia", "LY": "Libya", "MA": "Morocco", "MC": "Monaco",
    "MD": "Moldova", "ME": "Montenegro", "MG": "Madagascar", "MK": "North Macedonia", "ML": "Mali",
    "MM": "Myanmar", "MN": "Mongolia", "MO": "Macau", "MT": "Malta", "MU": "Mauritius",
    "MV": "Maldives", "MW": "Malawi", "MX": "Mexico", "MY": "Malaysia", "MZ": "Mozambique",
    "NA": "Namibia", "NE": "Niger", "NG": "Nigeria", "NI": "Nicaragua", "NL": "Netherlands",
    "NO": "Norway", "NP": "Nepal", "NZ": "New Zealand", "OM": "Oman", "PA": "Panama", "PE": "Peru",
    "PG": "Papua New Guinea", "PH": "Philippines", "PK": "Pakistan", "PL": "Poland", "PT": "Portugal",
    "PY": "Paraguay", "QA": "Qatar", "RO": "Romania", "RS": "Serbia", "RU": "Russia", "RW": "Rwanda",
    "SA": "Saudi Arabia", "SB": "Solomon Islands", "SC": "Seychelles", "SD": "Sudan", "SE": "Sweden",
    "SG": "Singapore", "SI": "Slovenia", "SK": "Slovakia", "SL": "Sierra Leone", "SM": "San Marino",
    "SN": "Senegal", "SO": "Somalia", "SR": "Suriname", "SV": "El Salvador", "SY": "Syria",
    "SZ": "Eswatini", "TD": "Chad", "TG": "Togo", "TH": "Thailand", "TJ": "Tajikistan",
    "TL": "Timor-Leste", "TM": "Turkmenistan", "TN": "Tunisia", "TO": "Tonga", "TR": "Turkey",
    "TT": "Trinidad and Tobago", "TW": "Taiwan", "TZ": "Tanzania", "UA": "Ukraine", "UG": "Uganda",
    "US": "United States", "UY": "Uruguay", "UZ": "Uzbekistan", "VA": "Vatican City",
    "VE": "Venezuela", "VN": "Vietnam", "VU": "Vanuatu", "WS": "Samoa", "YE": "Yemen",
    "ZA": "South Africa", "ZM": "Zambia", "ZW": "Zimbabwe"
}

_rg_module = None
_rg_initialized = False

def _get_rg():
    global _rg_module, _rg_initialized
    if not _rg_initialized:
        try:
            import reverse_geocoder as rg
            _rg_module = rg
        except ImportError:
            logger.debug("reverse-geocoder library not installed; fallback reverse geocoding active.")
            _rg_module = None
        _rg_initialized = True
    return _rg_module


def reverse_geocode(lat: float, lon: float) -> Dict[str, str]:
    """
    Offline reverse geocoding from GPS coordinates to human-readable City, State, Country.
    Runs locally in microseconds using KD-Tree of global populated places.
    """
    if lat is None or lon is None:
        return {}

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return {}

    rg = _get_rg()
    if rg is None:
        return {
            "city": "",
            "country": "",
            "country_code": "",
            "location_str": f"{lat_f:.4f}°, {lon_f:.4f}°"
        }

    try:
        # rg.search expects tuple of coordinates or list of tuples
        results = rg.search([(lat_f, lon_f)], mode=1)
        if not results:
            return {}

        res = results[0]
        raw_name = res.get("name", "").strip()
        admin1 = res.get("admin1", "").strip()
        cc = res.get("cc", "").strip().upper()
        country_name = COUNTRY_MAP.get(cc, cc)

        # Clean city name (e.g. "Budapest II. keruelet" -> "Budapest", "Arrondissement de Paris" -> "Paris")
        city_name = raw_name
        for prefix in ["Arrondissement de ", "District of ", "Commune of "]:
            if city_name.startswith(prefix):
                city_name = city_name[len(prefix):]
        
        # If raw_name contains district or roman numerals (e.g. "Budapest II. keruelet")
        if " keruelet" in city_name.lower() or " kerület" in city_name.lower():
            city_name = city_name.split()[0]

        # Prefer admin1 if raw name is very generic/suburb
        if admin1 and admin1.lower() in ["budapest", "paris", "berlin", "vienna", "prague", "rome", "tokyo", "london"]:
            city_name = admin1

        location_parts = []
        if city_name:
            location_parts.append(city_name)
        elif admin1:
            location_parts.append(admin1)

        if country_name and (not location_parts or country_name != location_parts[-1]):
            location_parts.append(country_name)

        location_str = ", ".join(location_parts) if location_parts else country_name or f"{lat_f:.4f}°, {lon_f:.4f}°"

        return {
            "city": city_name,
            "admin1": admin1,
            "country": country_name,
            "country_code": cc,
            "location_str": location_str
        }
    except Exception as e:
        logger.debug(f"Reverse geocode lookup notice for ({lat}, {lon}): {e}")
        return {}


def format_location_context(metadata: Optional[Dict[str, Any]]) -> str:
    """
    Constructs a clean location description string from metadata without raw numeric coordinates.
    """
    if not isinstance(metadata, dict):
        return ""

    # Check if location_name or city/country already precomputed
    loc_str = metadata.get("location_name") or metadata.get("location")
    if loc_str and not any(ch in str(loc_str) for ch in ["°", "lat", "lon"]):
        return str(loc_str)

    lat = metadata.get("gps_lat")
    lon = metadata.get("gps_lon")
    if lat is not None and lon is not None:
        geocoded = reverse_geocode(lat, lon)
        if geocoded.get("location_str"):
            return geocoded["location_str"]

    city = metadata.get("city")
    country = metadata.get("country")
    if city and country:
        return f"{city}, {country}"
    elif city or country:
        return str(city or country)

    return ""
