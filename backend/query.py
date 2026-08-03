from pydantic import BaseModel
from pydantic_ai import Agent


class HistoricalMoment(BaseModel):
    year: int  # must be one of: 1900,1914,1920,1930,1938,1945,1960,1994,2000
    title: str
    description: str


class QueryResponse(BaseModel):
    answer: str
    regions: list[str]  # country_code values
    year_start: int
    year_end: int
    moments: list[HistoricalMoment]
    citations: list[str]


agent = Agent(
    "anthropic:claude-sonnet-5",
    output_type=QueryResponse,
    system_prompt="""You are a historical atlas AI. Answer questions about European political and military history 1900-2000.

    Return structured output with:
    - answer: clear explanation
    - regions: list of country names exactly as they appear in historical maps (e.g. "German Empire", "Austria-Hungary", "France")
    - year_start/year_end: the time range relevant to the question
    - moments: key events, each with a year (must be from: 1900,1914,1920,1930,1938,1945,1960,1994,2000)
    - citations: Wikipedia article titles or book references
    """,
)
