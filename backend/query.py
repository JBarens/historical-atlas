from pydantic import BaseModel
from pydantic_ai import Agent


class HistoricalMoment(BaseModel):
    year: int  # must be one of: 1900,1914,1920,1930,1938,1945,1960,1994,2000
    title: str
    description: str
    regions: list[str]  # countries most relevant to THIS moment specifically


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
- answer: clear explanation (2-4 sentences)
- regions: the countries that are the geographic SUBJECT of the query — only the directly involved states, not observers or minor actors
- year_start/year_end: the time range relevant to the question (use years from: 1900,1914,1920,1930,1938,1945,1960,1994,2000)
- moments: 3-5 key events, each pinned to a year from [1900,1914,1920,1930,1938,1945,1960,1994,2000]. Each moment's `regions` must list only the countries physically central to THAT event.
- citations: Wikipedia article titles or book references

CRITICAL — use these exact historical names as they appeared on maps:
- Pre-1918: "German Empire", "Austria-Hungary", "Ottoman Empire", "Russia", "United Kingdom of Great Britain and Ireland", "France", "Kingdom of Italy", "Kingdom of Serbia", "Kingdom of Romania", "Kingdom of Bulgaria", "Kingdom of Greece"
- 1920-1938: "Germany", "Austria", "Hungary", "Czechoslovakia", "Yugoslavia", "Poland", "Soviet Union", "Turkey", "France", "United Kingdom", "Kingdom of Italy"
- 1938-1945: "Nazi Germany", "Soviet Union", "France", "United Kingdom", "Kingdom of Italy", "Poland", "Czechoslovakia"
- Post-1945: "West Germany", "East Germany", "Soviet Union", "France", "United Kingdom", "Poland", "Czechoslovakia", "Yugoslavia", "Romania", "Bulgaria", "Hungary", "Austria"
- Post-1991: "Germany", "Russia", "France", "United Kingdom", "Poland", "Czech Republic", "Slovakia", "Croatia", "Slovenia", "Bosnia and Herzegovina", "Serbia", "Ukraine"

Only include a country in regions if it is geographically and politically central to the event — not peripheral powers, not allies who played minor roles.""",
)
