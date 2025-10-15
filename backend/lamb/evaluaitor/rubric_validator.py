"""
Rubric Validation Module for LAMB Evaluaitor feature
Validates rubric JSON structure and data integrity.
"""

import json
import logging
from typing import Dict, List, Tuple, Optional, Any


class RubricValidator:
    """Validator for rubric data structures"""

    @staticmethod
    def validate_rubric_structure(rubric_data: dict, require_rubric_id: bool = True) -> Tuple[bool, str]:
        """
        Validate complete rubric structure

        Args:
            rubric_data: Rubric JSON data
            require_rubric_id: If False, rubricId is optional (for AI-generated rubrics)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(rubric_data, dict):
            return False, "Rubric data must be a JSON object"

        # Required fields
        required_fields = ['title', 'description', 'metadata', 'criteria', 'scoringType', 'maxScore']
        if require_rubric_id:
            required_fields.insert(0, 'rubricId')
            
        for field in required_fields:
            if field not in rubric_data:
                return False, f"Missing required field: {field}"

        # Validate metadata
        metadata_result = RubricValidator.validate_metadata(rubric_data.get('metadata', {}))
        if not metadata_result[0]:
            return metadata_result

        # Validate criteria
        criteria = rubric_data.get('criteria', [])
        if not isinstance(criteria, list) or len(criteria) == 0:
            return False, "Rubric must have at least one criterion"

        for i, criterion in enumerate(criteria):
            criterion_result = RubricValidator.validate_criterion(criterion)
            if not criterion_result[0]:
                return False, f"Criterion {i}: {criterion_result[1]}"

        # Validate scoring type
        valid_scoring_types = ['points', 'percentage', 'holistic', 'single-point', 'checklist']
        if rubric_data.get('scoringType') not in valid_scoring_types:
            return False, f"Invalid scoring type. Must be one of: {', '.join(valid_scoring_types)}"

        # Validate max score
        max_score = rubric_data.get('maxScore')
        if not isinstance(max_score, (int, float)) or max_score <= 0:
            return False, "maxScore must be a positive number"

        # Validate rubricId format (should be UUID-like) - only if required
        if require_rubric_id:
            rubric_id = rubric_data.get('rubricId', '')
            if not isinstance(rubric_id, str) or len(rubric_id) < 10:
                return False, "rubricId must be a valid unique identifier"

        return True, ""

    @staticmethod
    def validate_metadata(metadata: dict) -> Tuple[bool, str]:
        """
        Validate metadata structure

        Args:
            metadata: Metadata object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(metadata, dict):
            return False, "Metadata must be a JSON object"

        # Required timestamp fields
        required_fields = ['createdAt', 'modifiedAt']
        for field in required_fields:
            if field not in metadata:
                return False, f"Missing required metadata field: {field}"

        # Validate subject (optional, but if present must be a string)
        if 'subject' in metadata:
            subject = metadata.get('subject')
            if subject is not None and not isinstance(subject, str):
                return False, "Subject must be a string"

        # Validate grade level (optional, but if present must be a string)
        if 'gradeLevel' in metadata:
            grade_level = metadata.get('gradeLevel')
            if grade_level is not None and not isinstance(grade_level, str):
                return False, "Grade level must be a string"

        # Optional fields validation
        if 'author' in metadata and not isinstance(metadata['author'], str):
            return False, "Author must be a string"

        if 'version' in metadata and not isinstance(metadata['version'], str):
            return False, "Version must be a string"

        if 'tags' in metadata:
            if not isinstance(metadata['tags'], list):
                return False, "Tags must be an array"
            for tag in metadata['tags']:
                if not isinstance(tag, str):
                    return False, "All tags must be strings"

        return True, ""

    @staticmethod
    def validate_criterion(criterion: dict) -> Tuple[bool, str]:
        """
        Validate criterion structure

        Args:
            criterion: Criterion object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(criterion, dict):
            return False, "Criterion must be a JSON object"

        # Required fields
        required_fields = ['id', 'name', 'description', 'weight', 'levels']
        for field in required_fields:
            if field not in criterion:
                return False, f"Missing required criterion field: {field}"

        # Validate ID
        criterion_id = criterion.get('id', '')
        if not isinstance(criterion_id, str) or len(criterion_id.strip()) == 0:
            return False, "Criterion id must be a non-empty string"

        # Validate name
        name = criterion.get('name', '')
        if not isinstance(name, str) or len(name.strip()) == 0:
            return False, "Criterion name must be a non-empty string"

        # Validate description
        description = criterion.get('description', '')
        if not isinstance(description, str) or len(description.strip()) == 0:
            return False, "Criterion description must be a non-empty string"

        # Validate weight
        weight = criterion.get('weight')
        if not isinstance(weight, (int, float)) or weight < 0:
            return False, "Criterion weight must be a non-negative number"

        # Validate levels
        levels = criterion.get('levels', [])
        if not isinstance(levels, list) or len(levels) < 2:
            return False, "Criterion must have at least 2 levels"

        # Track unique IDs and scores within this criterion
        level_ids = set()
        level_scores = set()

        for i, level in enumerate(levels):
            level_result = RubricValidator.validate_level(level)
            if not level_result[0]:
                return False, f"Level {i}: {level_result[1]}"

            # Check for duplicate IDs within criterion
            level_id = level.get('id', '')
            if level_id in level_ids:
                return False, f"Duplicate level id within criterion: {level_id}"
            level_ids.add(level_id)

            # Check for duplicate scores within criterion (allow if intentional)
            level_score = level.get('score')
            if level_score in level_scores:
                logging.warning(f"Duplicate score {level_score} in criterion {criterion_id}")
            level_scores.add(level_score)

        # Optional fields
        if 'order' in criterion:
            order = criterion.get('order')
            if not isinstance(order, int) or order < 0:
                return False, "Criterion order must be a non-negative integer"

        return True, ""

    @staticmethod
    def validate_level(level: dict) -> Tuple[bool, str]:
        """
        Validate level structure

        Args:
            level: Level object

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not isinstance(level, dict):
            return False, "Level must be a JSON object"

        # Required fields
        required_fields = ['id', 'score', 'label', 'description']
        for field in required_fields:
            if field not in level:
                return False, f"Missing required level field: {field}"

        # Validate ID
        level_id = level.get('id', '')
        if not isinstance(level_id, str) or len(level_id.strip()) == 0:
            return False, "Level id must be a non-empty string"

        # Validate score
        score = level.get('score')
        if not isinstance(score, (int, float)):
            return False, "Level score must be a number"

        # Validate label
        label = level.get('label', '')
        if not isinstance(label, str) or len(label.strip()) == 0:
            return False, "Level label must be a non-empty string"

        # Validate description
        description = level.get('description', '')
        if not isinstance(description, str) or len(description.strip()) == 0:
            return False, "Level description must be a non-empty string"

        # Optional fields
        if 'order' in level:
            order = level.get('order')
            if not isinstance(order, int) or order < 0:
                return False, "Level order must be a non-negative integer"

        return True, ""

    @staticmethod
    def validate_imported_rubric(rubric_json: str) -> Tuple[bool, dict, str]:
        """
        Validate a rubric JSON string for import

        Args:
            rubric_json: JSON string of rubric data

        Returns:
            Tuple of (is_valid, parsed_data, error_message)
        """
        try:
            # Parse JSON
            rubric_data = json.loads(rubric_json)
        except json.JSONDecodeError as e:
            return False, {}, f"Invalid JSON format: {e}"

        # Validate structure
        is_valid, error_message = RubricValidator.validate_rubric_structure(rubric_data)

        return is_valid, rubric_data, error_message

    @staticmethod
    def sanitize_rubric_data(rubric_data: dict) -> dict:
        """
        Sanitize and normalize rubric data

        Args:
            rubric_data: Raw rubric data

        Returns:
            Sanitized rubric data
        """
        # Create a deep copy to avoid modifying original
        sanitized = json.loads(json.dumps(rubric_data))

        # Ensure proper data types
        if 'maxScore' in sanitized:
            try:
                sanitized['maxScore'] = float(sanitized['maxScore'])
            except (ValueError, TypeError):
                sanitized['maxScore'] = 10.0

        # Ensure weights are numbers
        if 'criteria' in sanitized:
            for criterion in sanitized['criteria']:
                if 'weight' in criterion:
                    try:
                        criterion['weight'] = float(criterion['weight'])
                    except (ValueError, TypeError):
                        criterion['weight'] = 0.0

                if 'levels' in criterion:
                    for level in criterion['levels']:
                        if 'score' in level:
                            try:
                                level['score'] = float(level['score'])
                            except (ValueError, TypeError):
                                level['score'] = 0.0

        return sanitized

    @staticmethod
    def generate_default_rubric(title: str = "New Rubric") -> dict:
        """
        Generate a default rubric structure

        Args:
            title: Title for the new rubric

        Returns:
            Default rubric data
        """
        import uuid
        from datetime import datetime

        now = datetime.now().isoformat()

        return {
            "rubricId": str(uuid.uuid4()),
            "title": title,
            "description": "A new rubric for assessing student work",
            "metadata": {
                "subject": "General",
                "gradeLevel": "General",
                "createdAt": now,
                "modifiedAt": now
            },
            "criteria": [
                {
                    "id": "criterion-1",
                    "name": "Content Quality",
                    "description": "Quality and accuracy of content",
                    "weight": 50,
                    "order": 0,
                    "levels": [
                        {
                            "id": "level-exemplary",
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Content is comprehensive, accurate, and demonstrates deep understanding",
                            "order": 0
                        },
                        {
                            "id": "level-proficient",
                            "score": 3,
                            "label": "Proficient",
                            "description": "Content is accurate and demonstrates good understanding",
                            "order": 1
                        },
                        {
                            "id": "level-developing",
                            "score": 2,
                            "label": "Developing",
                            "description": "Content has some accuracy but demonstrates limited understanding",
                            "order": 2
                        },
                        {
                            "id": "level-beginning",
                            "score": 1,
                            "label": "Beginning",
                            "description": "Content is inaccurate or demonstrates minimal understanding",
                            "order": 3
                        }
                    ]
                },
                {
                    "id": "criterion-2",
                    "name": "Presentation",
                    "description": "Organization and clarity of presentation",
                    "weight": 50,
                    "order": 1,
                    "levels": [
                        {
                            "id": "level-exemplary",
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Work is exceptionally well-organized and presented",
                            "order": 0
                        },
                        {
                            "id": "level-proficient",
                            "score": 3,
                            "label": "Proficient",
                            "description": "Work is well-organized and clearly presented",
                            "order": 1
                        },
                        {
                            "id": "level-developing",
                            "score": 2,
                            "label": "Developing",
                            "description": "Work is somewhat organized but presentation needs improvement",
                            "order": 2
                        },
                        {
                            "id": "level-beginning",
                            "score": 1,
                            "label": "Beginning",
                            "description": "Work is poorly organized and difficult to follow",
                            "order": 3
                        }
                    ]
                }
            ],
            "scoringType": "points",
            "maxScore": 10
        }
