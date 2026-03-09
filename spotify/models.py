from dataclasses import dataclass


@dataclass
class ArtistSearch:
    spotify_id: str
    name: str
    image_url: str | None
    match_score: float


@dataclass
class TrackInfo:
    spotify_id: str
    name: str
    preview_url: str | None
