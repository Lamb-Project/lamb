"""
AI Rubric Generator with JSON Recovery Strategies

Generates educational rubrics using LLM with robust JSON extraction and validation.
"""

import json
import re
import logging
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
from openai import OpenAI
import os

from .prompt_loader import get_rubric_generation_prompt
from .rubric_validator import RubricValidator
from lamb.completions.org_config_resolver import OrganizationConfigResolver

logger = logging.getLogger(__name__)


class AIRubricGenerator:
    """
    AI-powered rubric generator with multiple JSON recovery strategies.
    """
    
    def __init__(self, user_email: str):
        """
        Initialize generator with user's organization configuration.
        
        Args:
            user_email: Email of user (for organization config resolution)
        """
        self.user_email = user_email
        self.config_resolver = OrganizationConfigResolver(user_email)
        
        # Get OpenAI configuration from organization
        openai_config = self.config_resolver.get_provider_config("openai")
        
        if not openai_config:
            raise ValueError("OpenAI configuration not found for organization")
        
        self.api_key = openai_config.get("api_key")
        self.base_url = openai_config.get("base_url", "https://api.openai.com/v1")
        self.default_model = openai_config.get("default_model", "gpt-4o-mini")
        
        if not self.api_key:
            raise ValueError("OpenAI API key not configured for organization")
        
        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        
        logger.info(f"AI Rubric Generator initialized for {user_email} with model {self.default_model}")
    
    
    def generate_rubric(
        self,
        user_prompt: str,
        language: str = 'en',
        model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a rubric from user's natural language prompt.
        
        Args:
            user_prompt: User's description of desired rubric
            language: Language code (en, es, eu, ca)
            model: Optional specific model (defaults to org default)
            
        Returns:
            Dictionary with:
                - success: bool
                - rubric: dict (if successful)
                - markdown: str (if successful)
                - explanation: str (if successful)
                - prompt_used: str (for debugging)
                - error: str (if failed)
                - raw_response: str (if failed)
                - allow_manual_edit: bool (if failed with Strategy E)
        """
        # Load and render prompt template
        final_prompt = get_rubric_generation_prompt(user_prompt, language)
        
        if not final_prompt:
            return {
                "success": False,
                "error": f"Could not load prompt template for language '{language}'",
                "allow_manual_edit": False
            }
        
        # Use specified model or default
        model_to_use = model or self.default_model
        
        logger.info(f"Generating rubric with model {model_to_use}, language {language}")
        logger.debug(f"Prompt length: {len(final_prompt)} characters")
        
        try:
            # Call LLM (Strategy 1 - Initial attempt)
            response = self._call_llm(final_prompt, model_to_use)
            
            # Strategy A: Try to extract and parse JSON
            rubric_data, explanation = self._extract_json_strategy_a(response)
            
            if rubric_data:
                # Validate rubric structure (rubricId not required for AI-generated rubrics)
                is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data, require_rubric_id=False)
                
                if is_valid:
                    # Success! Generate markdown and return
                    markdown = self._generate_markdown(rubric_data)
                    
                    return {
                        "success": True,
                        "rubric": rubric_data,
                        "markdown": markdown,
                        "explanation": explanation or "Rubric generated successfully",
                        "prompt_used": final_prompt
                    }
                else:
                    logger.warning(f"Initial JSON extraction succeeded but validation failed: {error_msg}")
                    # Fall through to Strategy D
            
            # Strategy D: Retry with stricter instructions
            logger.info("Strategy A failed, attempting Strategy D (retry with strict JSON)")
            retry_result = self._retry_with_strict_json(user_prompt, response, model_to_use, language)
            
            if retry_result["success"]:
                return retry_result
            
            # Strategy E: Return for manual editing
            logger.warning("All strategies failed, returning for manual edit")
            return {
                "success": False,
                "error": "Could not parse valid rubric from LLM response",
                "raw_response": response,
                "allow_manual_edit": True,
                "prompt_used": final_prompt
            }
            
        except Exception as e:
            logger.error(f"Error generating rubric: {e}")
            return {
                "success": False,
                "error": f"Error calling LLM: {str(e)}",
                "allow_manual_edit": False
            }
    
    
    def _call_llm(self, prompt: str, model: str, temperature: float = 0.7) -> str:
        """
        Call LLM with the prompt.
        
        Args:
            prompt: The complete prompt to send
            model: Model identifier
            temperature: Temperature for generation (0.7 for creative but controlled)
            
        Returns:
            Raw text response from LLM
        """
        try:
            completion = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=4000  # Generous limit for complete rubric
            )
            
            response_text = completion.choices[0].message.content
            logger.debug(f"LLM response length: {len(response_text)} characters")
            
            return response_text
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            raise
    
    
    def _extract_json_strategy_a(self, llm_response: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Strategy A: Extract JSON from markdown code blocks or raw JSON.
        
        Tries multiple patterns:
        1. ```json ... ``` blocks
        2. ``` ... ``` blocks (no language specified)
        3. Raw JSON starting with {
        
        Args:
            llm_response: Raw LLM response text
            
        Returns:
            Tuple of (rubric_dict, explanation) or (None, None) if extraction fails
        """
        # Try pattern 1: ```json ... ```
        pattern_json = r'```json\s*(\{.*?\})\s*```'
        match = re.search(pattern_json, llm_response, re.DOTALL | re.IGNORECASE)
        
        if match:
            logger.debug("Found JSON in ```json block")
            return self._parse_json_response(match.group(1))
        
        # Try pattern 2: ``` ... ``` (generic code block)
        pattern_code = r'```\s*(\{.*?\})\s*```'
        match = re.search(pattern_code, llm_response, re.DOTALL)
        
        if match:
            logger.debug("Found JSON in generic ``` block")
            return self._parse_json_response(match.group(1))
        
        # Try pattern 3: Raw JSON (starts with { and ends with })
        # Find the outermost JSON object
        try:
            # Find first { and last }
            start = llm_response.find('{')
            end = llm_response.rfind('}')
            
            if start != -1 and end != -1 and end > start:
                json_str = llm_response[start:end+1]
                logger.debug("Attempting to parse raw JSON from response")
                return self._parse_json_response(json_str)
        except Exception as e:
            logger.debug(f"Raw JSON extraction failed: {e}")
        
        logger.warning("Could not extract JSON from LLM response using Strategy A")
        return None, None
    
    
    def _parse_json_response(self, json_str: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Parse JSON string and extract rubric and explanation.
        
        Expected format:
        {
          "rubric": { ... },
          "explanation": "..."
        }
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Tuple of (rubric_dict, explanation) or (None, None) if parsing fails
        """
        try:
            data = json.loads(json_str)
            
            # Check if response has expected structure
            if isinstance(data, dict):
                rubric = data.get('rubric')
                explanation = data.get('explanation', '')
                
                if rubric and isinstance(rubric, dict):
                    logger.debug("Successfully parsed JSON with rubric structure")
                    return rubric, explanation
                else:
                    logger.warning("JSON parsed but missing 'rubric' key or wrong type")
            
        except json.JSONDecodeError as e:
            logger.debug(f"JSON parse error: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error parsing JSON: {e}")
        
        return None, None
    
    
    def _retry_with_strict_json(
        self,
        original_prompt: str,
        failed_response: str,
        model: str,
        language: str
    ) -> Dict[str, Any]:
        """
        Strategy D: Retry LLM call with strict JSON formatting instructions.
        
        Args:
            original_prompt: Original user prompt
            failed_response: The response that failed to parse
            model: Model to use
            language: Language for error messages
            
        Returns:
            Result dictionary (same format as generate_rubric)
        """
        # Create strict retry prompt
        strict_prompt = self._create_strict_json_prompt(original_prompt, language)
        
        logger.info("Retrying with strict JSON formatting instructions")
        
        try:
            retry_response = self._call_llm(strict_prompt, model, temperature=0.3)  # Lower temp for more deterministic
            
            # Try to extract JSON again
            rubric_data, explanation = self._extract_json_strategy_a(retry_response)
            
            if rubric_data:
                # Validate (rubricId not required for AI-generated rubrics)
                is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data, require_rubric_id=False)
                
                if is_valid:
                    markdown = self._generate_markdown(rubric_data)
                    logger.info("Strategy D succeeded on retry")
                    
                    return {
                        "success": True,
                        "rubric": rubric_data,
                        "markdown": markdown,
                        "explanation": explanation or "Rubric generated on retry",
                        "prompt_used": strict_prompt,
                        "retry_attempt": True
                    }
                else:
                    logger.warning(f"Retry validation failed: {error_msg}")
            else:
                logger.warning("Strategy D: Could not extract JSON from retry response")
            
        except Exception as e:
            logger.error(f"Error in retry attempt: {e}")
        
        return {"success": False}
    
    
    def _create_strict_json_prompt(self, user_prompt: str, language: str) -> str:
        """
        Create a strict JSON-only prompt for retry attempt.
        
        Args:
            user_prompt: Original user request
            language: Language code
            
        Returns:
            Strict prompt asking for JSON only
        """
        # Language-specific instructions
        instructions = {
            'en': "Your previous response could not be parsed. Please provide ONLY valid JSON with no additional text.",
            'es': "Tu respuesta anterior no pudo ser analizada. Por favor proporciona SOLO JSON válido sin texto adicional.",
            'eu': "Zure aurreko erantzuna ezin izan da analizatu. Mesedez eman BAKARRIK JSON baliozkoa testu gehigarririk gabe.",
            'ca': "La teva resposta anterior no es va poder analitzar. Si us plau proporciona NOMÉS JSON vàlid sense text addicional."
        }
        
        instruction = instructions.get(language, instructions['en'])
        
        prompt = f"""{instruction}

User's request: "{user_prompt}"

Required JSON format (respond with ONLY this, no other text):

{{
  "rubric": {{
    "title": "string",
    "description": "string",
    "metadata": {{
      "subject": "string",
      "gradeLevel": "string",
      "createdAt": "{datetime.utcnow().isoformat()}Z",
      "modifiedAt": "{datetime.utcnow().isoformat()}Z"
    }},
    "criteria": [
      {{
        "id": "criterion-1",
        "name": "string",
        "description": "string",
        "weight": 25,
        "order": 0,
        "levels": [
          {{
            "id": "level-1-1",
            "score": 4,
            "label": "string",
            "description": "string",
            "order": 0
          }}
        ]
      }}
    ],
    "scoringType": "points",
    "maxScore": 10
  }},
  "explanation": "string"
}}

Example:
{{
  "rubric": {{
    "title": "Essay Writing Rubric",
    "description": "Assessment for argumentative essays",
    "metadata": {{
      "subject": "English",
      "gradeLevel": "9-12",
      "createdAt": "{datetime.utcnow().isoformat()}Z",
      "modifiedAt": "{datetime.utcnow().isoformat()}Z"
    }},
    "criteria": [
      {{
        "id": "criterion-1",
        "name": "Thesis Statement",
        "description": "Quality of main argument",
        "weight": 100,
        "order": 0,
        "levels": [
          {{
            "id": "level-1-1",
            "score": 4,
            "label": "Exemplary",
            "description": "Clear and compelling thesis",
            "order": 0
          }},
          {{
            "id": "level-1-2",
            "score": 3,
            "label": "Proficient",
            "description": "Clear thesis",
            "order": 1
          }},
          {{
            "id": "level-1-3",
            "score": 2,
            "label": "Developing",
            "description": "Vague thesis",
            "order": 2
          }},
          {{
            "id": "level-1-4",
            "score": 1,
            "label": "Beginning",
            "description": "Missing thesis",
            "order": 3
          }}
        ]
      }}
    ],
    "scoringType": "points",
    "maxScore": 10
  }},
  "explanation": "This rubric focuses on the thesis as the core element"
}}

Respond with ONLY the JSON object for the user's request. No markdown, no explanations, just JSON.
"""
        return prompt
    
    
    def _generate_markdown(self, rubric_data: Dict[str, Any]) -> str:
        """
        Generate markdown representation of rubric.
        
        Args:
            rubric_data: Validated rubric JSON structure
            
        Returns:
            Markdown formatted rubric
        """
        md_parts = []
        
        # Header
        title = rubric_data.get('title', 'Untitled Rubric')
        description = rubric_data.get('description', '')
        
        md_parts.append(f"# {title}\n")
        if description:
            md_parts.append(f"**Description:** {description}\n")
        
        # Metadata
        metadata = rubric_data.get('metadata', {})
        if metadata.get('subject'):
            md_parts.append(f"**Subject:** {metadata['subject']}")
        if metadata.get('gradeLevel'):
            md_parts.append(f"**Grade Level:** {metadata['gradeLevel']}")
        
        scoring_type = rubric_data.get('scoringType', 'points')
        max_score = rubric_data.get('maxScore', 10)
        md_parts.append(f"**Scoring Type:** {scoring_type}")
        md_parts.append(f"**Maximum Score:** {max_score}\n")
        
        md_parts.append("---\n")
        md_parts.append("## Criteria and Performance Levels\n")
        
        # Build table
        criteria = rubric_data.get('criteria', [])
        
        if not criteria:
            md_parts.append("*No criteria defined*\n")
            return "\n".join(md_parts)
        
        # Get all unique levels across criteria (for table header)
        all_levels = criteria[0].get('levels', []) if criteria else []
        
        # Table header
        header_row = "| Criterion |"
        separator_row = "|-----------|"
        
        for level in all_levels:
            label = level.get('label', 'Level')
            score = level.get('score', '')
            header_row += f" {label} ({score}) |"
            separator_row += "----------------|"
        
        md_parts.append(header_row)
        md_parts.append(separator_row)
        
        # Table rows (one per criterion)
        for criterion in criteria:
            name = criterion.get('name', 'Unnamed')
            desc = criterion.get('description', '')
            weight = criterion.get('weight', 0)
            levels = criterion.get('levels', [])
            
            # Build row
            row = f"| **{name}** ({weight} pts)"
            if desc:
                row += f"<br>{desc}"
            row += " |"
            
            # Add level descriptions
            for level in levels:
                level_desc = level.get('description', '')
                row += f" {level_desc} |"
            
            md_parts.append(row)
        
        # Footer
        md_parts.append("\n---\n")
        if metadata.get('createdAt'):
            created = metadata['createdAt'][:10]  # Just the date
            md_parts.append(f"*Created: {created}*")
        
        return "\n".join(md_parts)
    
    
    def _extract_json_strategy_a(self, llm_response: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Strategy A: Extract JSON from markdown code blocks or raw JSON.
        
        Returns:
            Tuple of (rubric_dict, explanation) or (None, None)
        """
        # Try markdown ```json blocks
        pattern_json = r'```json\s*(\{.*?\})\s*```'
        match = re.search(pattern_json, llm_response, re.DOTALL | re.IGNORECASE)
        
        if match:
            logger.debug("Found JSON in ```json block")
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                rubric = data.get('rubric') if isinstance(data, dict) else None
                explanation = data.get('explanation', '') if isinstance(data, dict) else ''
                return rubric, explanation
            except json.JSONDecodeError as e:
                logger.debug(f"JSON in code block is invalid: {e}")
        
        # Try generic ``` blocks
        pattern_code = r'```\s*(\{.*?\})\s*```'
        match = re.search(pattern_code, llm_response, re.DOTALL)
        
        if match:
            logger.debug("Found JSON in generic ``` block")
            json_str = match.group(1)
            try:
                data = json.loads(json_str)
                rubric = data.get('rubric') if isinstance(data, dict) else None
                explanation = data.get('explanation', '') if isinstance(data, dict) else ''
                return rubric, explanation
            except json.JSONDecodeError as e:
                logger.debug(f"JSON in code block is invalid: {e}")
        
        # Try raw JSON
        try:
            start = llm_response.find('{')
            end = llm_response.rfind('}')
            
            if start != -1 and end != -1 and end > start:
                json_str = llm_response[start:end+1]
                data = json.loads(json_str)
                
                rubric = data.get('rubric') if isinstance(data, dict) else None
                explanation = data.get('explanation', '') if isinstance(data, dict) else ''
                
                if rubric:
                    logger.debug("Extracted raw JSON successfully")
                    return rubric, explanation
        except json.JSONDecodeError as e:
            logger.debug(f"Raw JSON extraction failed: {e}")
        except Exception as e:
            logger.debug(f"Unexpected error in raw JSON extraction: {e}")
        
        return None, None
    
    
    def validate_and_fix_rubric(self, rubric_json: str) -> Dict[str, Any]:
        """
        Validate user-edited JSON and attempt basic fixes.
        
        Args:
            rubric_json: JSON string from user (potentially edited)
            
        Returns:
            Result dictionary with success status and rubric or error
        """
        try:
            data = json.loads(rubric_json)
            
            # Check if it's the full response format or just the rubric
            if 'rubric' in data:
                rubric_data = data['rubric']
                explanation = data.get('explanation', '')
            else:
                # Assume it's just the rubric itself
                rubric_data = data
                explanation = ''
            
            # Validate structure (rubricId not required - will be generated on save)
            is_valid, error_msg = RubricValidator.validate_rubric_structure(rubric_data, require_rubric_id=False)
            
            if is_valid:
                markdown = self._generate_markdown(rubric_data)
                return {
                    "success": True,
                    "rubric": rubric_data,
                    "markdown": markdown,
                    "explanation": explanation
                }
            else:
                return {
                    "success": False,
                    "error": f"Validation failed: {error_msg}"
                }
                
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"Invalid JSON: {str(e)}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Error validating rubric: {str(e)}"
            }


def generate_rubric_ai(
    user_prompt: str,
    user_email: str,
    language: str = 'en',
    model: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to generate a rubric using AI.
    
    Args:
        user_prompt: User's natural language description
        user_email: User's email (for org config)
        language: Language code (en, es, eu, ca)
        model: Optional specific model override
        
    Returns:
        Generation result dictionary
    """
    try:
        generator = AIRubricGenerator(user_email)
        return generator.generate_rubric(user_prompt, language, model)
    except Exception as e:
        logger.error(f"Error creating AI generator: {e}")
        return {
            "success": False,
            "error": f"Configuration error: {str(e)}",
            "allow_manual_edit": False
        }

