"""
Evaluator client – calls LAMB's internal completions API and parses scores.

Replaces LAMBA's LAMBAPIService (HTTP) with a direct in-process call to
``run_lamb_assistant``.
"""
import re
from typing import Dict, Any, Optional
from lamb.logging_config import get_logger

logger = get_logger(__name__, component="FILE_EVAL")


class EvaluatorClient:
    """Evaluate text using a LAMB assistant and extract a numeric score."""

    @staticmethod
    async def evaluate_text(text: str, evaluator_id: int) -> Dict[str, Any]:
        """Send *text* to the LAMB assistant identified by *evaluator_id*.

        Returns ``{"success": bool, "response": dict | None, "error": str | None}``.
        """
        from lamb.completions.main import run_lamb_assistant

        request_body = {
            "model": f"lamb_assistant.{evaluator_id}",
            "messages": [{"role": "user", "content": text}],
            "stream": False,
        }

        try:
            result = await run_lamb_assistant(request=request_body, assistant=int(evaluator_id))
            return {"success": True, "response": result}
        except Exception as exc:
            logger.error(f"run_lamb_assistant failed: {exc}")
            return {"success": False, "response": None, "error": str(exc)}

    # ------------------------------------------------------------------
    # Response validation / parsing (ported verbatim from LAMBA)
    # ------------------------------------------------------------------

    @staticmethod
    def validate_chat_completions_format(response: Dict[str, Any]) -> Dict[str, Any]:
        validation: Dict[str, Any] = {
            'is_valid': True,
            'format_detected': None,
            'issues': [],
            'structure': {},
        }

        if not isinstance(response, dict):
            validation['is_valid'] = False
            validation['issues'].append(f"Response is not a dict, got: {type(response).__name__}")
            return validation

        validation['structure']['top_level_keys'] = list(response.keys())

        if 'choices' in response:
            validation['format_detected'] = 'openai_chat_completions'
            choices = response.get('choices', [])
            if not isinstance(choices, list):
                validation['is_valid'] = False
                validation['issues'].append(f"'choices' is not a list, got: {type(choices).__name__}")
            elif len(choices) == 0:
                validation['is_valid'] = False
                validation['issues'].append("'choices' array is empty")
            else:
                choice = choices[0]
                validation['structure']['first_choice_keys'] = list(choice.keys()) if isinstance(choice, dict) else None
                if not isinstance(choice, dict):
                    validation['is_valid'] = False
                    validation['issues'].append(f"First choice is not a dict, got: {type(choice).__name__}")
                elif 'message' in choice:
                    message = choice.get('message', {})
                    validation['structure']['message_keys'] = list(message.keys()) if isinstance(message, dict) else None
                    if not isinstance(message, dict):
                        validation['is_valid'] = False
                        validation['issues'].append(f"'message' is not a dict")
                    elif 'content' not in message:
                        validation['is_valid'] = False
                        validation['issues'].append("'message' does not contain 'content' key")
                elif 'text' in choice:
                    validation['format_detected'] = 'openai_completions_legacy'
                else:
                    validation['is_valid'] = False
                    validation['issues'].append("First choice has neither 'message' nor 'text' key")
        elif 'content' in response:
            validation['format_detected'] = 'simple_content'
        elif 'text' in response:
            validation['format_detected'] = 'simple_text'
        else:
            validation['is_valid'] = False
            validation['format_detected'] = 'unknown'
            validation['issues'].append("Response doesn't match any known format")

        return validation

    @staticmethod
    def parse_evaluation_response(response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract score + feedback from the completions response."""
        try:
            if isinstance(response, dict) and response.get('success') is False:
                return {
                    'success': False,
                    'error': response.get('error', 'Unknown error'),
                    'score': None,
                    'comment': None,
                    'raw_response': response,
                }

            validation = EvaluatorClient.validate_chat_completions_format(response)

            content = None
            if 'response' in response and isinstance(response['response'], dict):
                inner = response['response']
                if 'choices' in inner and len(inner['choices']) > 0:
                    choice = inner['choices'][0]
                    content = choice.get('message', {}).get('content') or choice.get('text')

            if not content and 'choices' in response and len(response.get('choices', [])) > 0:
                choice = response['choices'][0]
                content = choice.get('message', {}).get('content') or choice.get('text')
            if not content and 'content' in response:
                content = response['content']
            if not content and 'text' in response:
                content = response['text']

            if content:
                result = EvaluatorClient._extract_score_and_feedback(content)
                result['success'] = True
                result['json_validation'] = validation
                return result

            return {
                'success': True,
                'score': None,
                'comment': str(response),
                'raw_response': response,
                'json_validation': validation,
            }
        except Exception as exc:
            return {
                'success': False,
                'error': f"Error parsing response: {exc}",
                'score': None,
                'comment': str(exc),
                'raw_response': response,
                'json_validation': {'is_valid': False, 'issues': [str(exc)]},
            }

    # ------------------------------------------------------------------
    # Score extraction – regex patterns ported verbatim from LAMBA
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_score_and_feedback(content: str) -> Dict[str, Any]:
        score = None

        patterns = [
            r'(?:NOTA\s+FINAL|FINAL\s+SCORE)\s*:\s*(\d+\.?\d*)',
            r'(?:#*\s*\**\s*)(?:Nota|Puntuación|Calificación)\s*(?:\**)\s*:\s*(\d+\.?\d*)',
            r'(?:#*\s*\**\s*)(?:Score|Grade|Mark)\s*(?:\**)\s*:\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*/\s*10\s*(?:puntos?|points?)?\s*$',
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                try:
                    candidate = float(match.group(1))
                    if 0 <= candidate <= 10:
                        score = candidate
                        break
                except (ValueError, IndexError):
                    pass

        return {'score': score, 'comment': content, 'raw_response': content}
