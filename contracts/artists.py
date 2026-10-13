"""[계약] on-stage GET /api/artists 응답의 에이전트용 부분집합. artist_context.md 참고."""

from datetime import date

from pydantic import BaseModel


class City(BaseModel):
    code: str
    name: str
    date: date


class Tour(BaseModel):
    badge: str
    titleKo: str
    year: int


class Stats(BaseModel):
    cities: int
    countries: int
    tracks: int


class Track(BaseModel):
    no: int
    title: str
    duration: str


class Artist(BaseModel):
    slug: str
    name: str
    nameKo: str
    news: str
    tour: Tour
    stats: Stats
    cities: list[City]
    tracks: list[Track]


class ArtistsResponse(BaseModel):
    artists: list[Artist]
