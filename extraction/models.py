from pydantic import BaseModel, Field
from typing import List

class Relationship(BaseModel):
    target: str = Field(..., description="The name of the related concept")
    type: str = Field(..., description="The type of relationship: requires, related_to, part_of")

class ExtractedConcept(BaseModel):
    concept_name: str = Field(..., description="The name of the concept")
    definition: str = Field(..., description="Concise definition based only on source material")
    keywords: List[str] = Field(..., description="Important keywords associated with the concept")
    relationships: List[Relationship] = Field(..., description="Relationships to other concepts explicitly stated")

class ExtractionResult(BaseModel):
    concepts: List[ExtractedConcept]
