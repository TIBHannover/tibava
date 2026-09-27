import base64
import hashlib
import json
import logging
import random
import re
from typing import List, Optional

import requests

from .communication import ExponentialBackoff

logger = logging.getLogger(__name__)

MAX_LABEL_LENGTH = 200
MAX_CANDIDATES = 3

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE | re.MULTILINE)

GEOLOCATION_LLM_SYSTEM_PROMPT = "You are a helpful assistant."

MAX_LOG_STRING_LEN = 300
SENSITIVE_HEADER_HINTS = ("authorization", "key", "token", "secret")


def mask_header(name: str, value: str) -> str:
    if any(hint in name.lower() for hint in SENSITIVE_HEADER_HINTS):
        if len(value) <= 8:
            return "***"
        return f"{value[:6]}***{value[-4:]}"
    return value


def summarize_for_log(value, max_len: int = MAX_LOG_STRING_LEN):
    if isinstance(value, str):
        if len(value) > max_len:
            # A truncated prefix alone is a poor signal for base64 images:
            # most encoders emit identical header bytes (JPEG's SOI/JFIF
            # segment, default quantization tables) regardless of image
            # content, so distinct frames and accidental duplicate frames
            # look the same in a short prefix. Hash the full string instead
            # so identical vs. distinct values are obvious at a glance.
            digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:12]
            return f"<string, {len(value)} chars, sha256={digest}> {value[:40]}..."
        return value
    if isinstance(value, list):
        return [summarize_for_log(v, max_len) for v in value]
    if isinstance(value, dict):
        return {k: summarize_for_log(v, max_len) for k, v in value.items()}
    return value

# Sample city names/coordinates used by the mock client and by the frontend's
# LOCATION_FIXTURE (frontend/src/plugins/geolocationSampleData.js), so a
# mocked run's predicted locations line up with what was already used to
# build/test the map UI.
SAMPLE_LOCATIONS = [
    {"label": "Anchorage, United States", "lat": 61.2181, "lon": -149.9003},
    {"label": "Honolulu, United States", "lat": 21.3069, "lon": -157.8583},
    {"label": "Vancouver, Canada", "lat": 49.2827, "lon": -123.1207},
    {"label": "San Francisco, United States", "lat": 37.7749, "lon": -122.4194},
    {"label": "Mexico City, Mexico", "lat": 19.4326, "lon": -99.1332},
    {"label": "New York, United States", "lat": 40.7128, "lon": -74.006},
    {"label": "Sao Paulo, Brazil", "lat": -23.5505, "lon": -46.6333},
    {"label": "Buenos Aires, Argentina", "lat": -34.6037, "lon": -58.3816},
    {"label": "Reykjavik, Iceland", "lat": 64.1466, "lon": -21.9426},
    {"label": "London, United Kingdom", "lat": 51.5072, "lon": -0.1276},
    {"label": "Paris, France", "lat": 48.8566, "lon": 2.3522},
    {"label": "Rome, Italy", "lat": 41.9028, "lon": 12.4964},
    {"label": "Cairo, Egypt", "lat": 30.0444, "lon": 31.2357},
    {"label": "Nairobi, Kenya", "lat": -1.2921, "lon": 36.8219},
    {"label": "Cape Town, South Africa", "lat": -33.9249, "lon": 18.4241},
    {"label": "Moscow, Russia", "lat": 55.7558, "lon": 37.6173},
    {"label": "Dubai, United Arab Emirates", "lat": 25.2048, "lon": 55.2708},
    {"label": "Mumbai, India", "lat": 19.076, "lon": 72.8777},
    {"label": "Delhi, India", "lat": 28.6139, "lon": 77.209},
    {"label": "Bangkok, Thailand", "lat": 13.7563, "lon": 100.5018},
    {"label": "Singapore", "lat": 1.3521, "lon": 103.8198},
    {"label": "Beijing, China", "lat": 39.9042, "lon": 116.4074},
    {"label": "Seoul, South Korea", "lat": 37.5665, "lon": 126.978},
    {"label": "Tokyo, Japan", "lat": 35.6762, "lon": 139.6503},
    {"label": "Manila, Philippines", "lat": 14.5995, "lon": 120.9842},
    {"label": "Jakarta, Indonesia", "lat": -6.2088, "lon": 106.8456},
    {"label": "Perth, Australia", "lat": -31.9505, "lon": 115.8605},
    {"label": "Sydney, Australia", "lat": -33.8688, "lon": 151.2093},
    {"label": "Melbourne, Australia", "lat": -37.8136, "lon": 144.9631},
    {"label": "Auckland, New Zealand", "lat": -36.8485, "lon": 174.7633},
]


DEFAULT_GEOLOCATION_PROMPT = (
    "You are given one or more video frames from the same shot of a video."
    " Identify the most likely real-world geographic location shown in"
    ' these frames. Respond with a JSON array of up to 3 candidate'
    ' locations, ranked from most to least likely, each an object with the'
    ' keys "label" (a short human-readable place name), "lat" and "lon"'
    ' (decimal degrees), and "confidence" (a number between 0 and 1). If no'
    " reasonable guess can be made, respond with an empty JSON array."
    " Respond with only the JSON array and no additional text."
)


def build_geolocation_prompt(
    year: Optional[str] = None, prompt: Optional[str] = None
) -> str:
    base_prompt = prompt if prompt else DEFAULT_GEOLOCATION_PROMPT
    if year:
        return f"{base_prompt} This footage is from approximately the year {year}."
    return base_prompt


class GeolocationLLMError(Exception):
    pass


class GeolocationLLMClient:
    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        max_attempts: int = 4,
        timeout: int = 120,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.max_attempts = max_attempts
        self.timeout = timeout
        self.backoff = ExponentialBackoff(
            init_backoff_ms=500, max_backoff_ms=8000, multiplier=2
        )

    def locate(self, images: List[bytes], prompt: str, request_label: str = "") -> List[dict]:
        # Chat-completions-style request (matches the Dartmouth chat gateway,
        # an OpenAI-compatible endpoint). Frames are attached as image_url
        # content parts alongside the text prompt in the user message -
        # unconfirmed against the real provider since the sample call this
        # was based on was text-only; this is the seam to adjust if the
        # provider expects a different multimodal shape.
        image_parts = [
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64.b64encode(image).decode('ascii')}"
                },
            }
            for image in images
        ]
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": GEOLOCATION_LLM_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [{"type": "text", "text": prompt}, *image_parts],
                },
            ],
            "stream": False,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        masked_headers = {k: mask_header(k, v) for k, v in headers.items()}

        last_error = None
        for attempt in range(self.max_attempts):
            logger.info(
                "Geolocation LLM request %s (attempt %s/%s): url=%s headers=%s payload=%s",
                request_label,
                attempt + 1,
                self.max_attempts,
                self.api_url,
                masked_headers,
                summarize_for_log(payload),
            )
            try:
                response = requests.post(
                    self.api_url, json=payload, headers=headers, timeout=self.timeout
                )
                logger.info(
                    "Geolocation LLM response %s (attempt %s/%s): status=%s body=%s",
                    request_label,
                    attempt + 1,
                    self.max_attempts,
                    response.status_code,
                    summarize_for_log(response.text, max_len=2000),
                )
                response.raise_for_status()
                try:
                    content = response.json()["choices"][0]["message"]["content"]
                except (KeyError, IndexError, TypeError, ValueError) as e:
                    raise GeolocationLLMError(
                        f"Unexpected LLM response shape: {e}; "
                        f"body={summarize_for_log(response.text, max_len=2000)}"
                    )
                return self._parse_response(content)
            except (requests.RequestException, GeolocationLLMError) as e:
                last_error = e
                logger.warning(
                    "Geolocation LLM request %s failed (attempt %s/%s): %s",
                    request_label,
                    attempt + 1,
                    self.max_attempts,
                    e,
                )
                if attempt < self.max_attempts - 1:
                    self.backoff.sleep(attempt)

        raise GeolocationLLMError(
            f"Geolocation LLM request {request_label} failed after "
            f"{self.max_attempts} attempts: {last_error}"
        )

    def _parse_response(self, text: str) -> List[dict]:
        cleaned = _JSON_FENCE_RE.sub("", text.strip()).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise GeolocationLLMError(f"Could not parse LLM response as JSON: {e}")

        if not isinstance(data, list):
            raise GeolocationLLMError("Expected a JSON array of candidate locations")

        candidates = []
        for item in data[:MAX_CANDIDATES]:
            try:
                candidates.append(
                    {
                        "label": str(item["label"])[:MAX_LABEL_LENGTH],
                        "lat": float(item["lat"]),
                        "lon": float(item["lon"]),
                        "confidence": float(item.get("confidence", 0.0)),
                    }
                )
            except (KeyError, TypeError, ValueError) as e:
                logger.warning("Skipping malformed geolocation candidate %r: %s", item, e)

        return candidates


class MockGeolocationLLMClient:
    """DEBUG-only stand-in for GeolocationLLMClient - same .locate() signature,
    no network calls or credentials required."""

    def locate(self, images: List[bytes], prompt: str, request_label: str = "") -> List[dict]:
        picks = random.sample(SAMPLE_LOCATIONS, random.randint(1, 3))
        candidates = [
            {**pick, "confidence": round(random.uniform(0.3, 0.98), 2)} for pick in picks
        ]
        candidates.sort(key=lambda c: c["confidence"], reverse=True)
        return candidates
