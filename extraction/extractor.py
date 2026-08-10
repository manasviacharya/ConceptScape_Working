import os
import json
import logging
import uuid
from typing import List, Dict, Any

from groq import Groq

class ConceptExtractor:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Missing GROQ_API_KEY environment variable")
        
        self.client = Groq(api_key=api_key)
        self.model_name = "llama-3.3-70b-versatile"
        
    def extract_from_chunk(self, text: str) -> List[Dict[str, Any]]:
        prompt = f"""
        Extract meaningful educational concepts from the following text.
        Extract actual concepts a student could learn, not generic terms.
        Concept extraction must be grounded STRICTLY in the supplied text.
        Do not invent concepts or definitions not present in the text.
        
        Text:
        {text}
        """
        
        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an AI educational extraction engine. You must output valid JSON matching this schema: {\"concepts\": [{\"concept_name\": \"string\", \"definition\": \"string\", \"keywords\": [\"string\"], \"relationships\": [{\"target\": \"string\", \"type\": \"requires|related_to|part_of\"}]}]}"
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result_json = response.choices[0].message.content
            result_data = json.loads(result_json)
            return result_data.get("concepts", [])
            
        except Exception as e:
            logging.error(f"Failed to extract concepts from chunk: {e}")
            return []

    def process_ingestion_result(self, ingestion_data: dict) -> List[Dict[str, Any]]:
        all_concepts = []
        subject_id = ingestion_data.get("subject_id")
        
        for resource in ingestion_data.get("resources", []):
            resource_id = resource.get("resource_id")
            resource_type = resource.get("resource_type")
            filename = resource.get("filename")
            
            for chunk in resource.get("content", []):
                text = chunk.get("text", "").strip()
                if not text:
                    continue
                    
                location_type = chunk.get("location_type")
                location_number = chunk.get("location_number")
                
                logging.info(f"Processing {resource_type.upper()} {location_type} {location_number}")
                
                concepts = self.extract_from_chunk(text)
                logging.info(f"Extracted {len(concepts)} concept mentions")
                
                for concept in concepts:
                    concept_mention = {
                        "concept_id": f"mention_{uuid.uuid4().hex[:8]}",
                        "concept_name": concept.get("concept_name", ""),
                        "definition": concept.get("definition", ""),
                        "keywords": concept.get("keywords", []),
                        "relationships": [
                            {"target": r.get("target"), "type": r.get("type")} 
                            for r in concept.get("relationships", [])
                        ],
                        "source_reference": {
                            "resource_id": resource_id,
                            "resource_type": resource_type,
                            "filename": filename
                        },
                        "workspace_id": subject_id
                    }
                    
                    if location_type == "page":
                        concept_mention["source_reference"]["page_number"] = location_number
                    elif location_type == "slide":
                        concept_mention["source_reference"]["slide_number"] = location_number
                        
                    all_concepts.append(concept_mention)
                    
        return all_concepts
