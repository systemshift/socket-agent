"""Confidence scoring for routing decisions."""

from typing import Any, Dict, List, Optional

from ..types import RouteResult


class ConfidenceScorer:
    """Scores confidence for routing decisions."""
    
    def __init__(self):
        """Initialize confidence scorer."""
        # Weights for different factors
        self.weights = {
            "pattern_match": 0.35,
            "keyword_overlap": 0.25,
            "action_match": 0.20,
            "parameter_completeness": 0.15,
            "schema_match": 0.05,
        }
    
    def score(
        self,
        text: str,
        stub: Any,
        extracted_args: Dict[str, Any],
        match_type: str = "unknown",
    ) -> float:
        """
        Calculate confidence score for a routing decision.
        
        Args:
            text: Original input text
            stub: Matched stub
            extracted_args: Extracted arguments
            match_type: Type of match (pattern, keyword, action)
            
        Returns:
            Confidence score between 0 and 1
        """
        scores = {}
        
        # Pattern match score
        scores["pattern_match"] = self._score_pattern_match(text, stub, match_type)
        
        # Keyword overlap score
        scores["keyword_overlap"] = self._score_keyword_overlap(text, stub)
        
        # Action match score
        scores["action_match"] = self._score_action_match(text, stub)
        
        # Parameter completeness score
        scores["parameter_completeness"] = self._score_parameter_completeness(
            extracted_args, stub
        )
        
        # Schema match score
        scores["schema_match"] = self._score_schema_match(extracted_args, stub)
        
        # Calculate weighted average
        total_score = 0
        total_weight = 0
        
        for factor, score in scores.items():
            weight = self.weights.get(factor, 0)
            total_score += score * weight
            total_weight += weight
        
        if total_weight > 0:
            final_score = total_score / total_weight
        else:
            final_score = 0.5  # Default middle confidence
        
        # Apply adjustments
        final_score = self._apply_adjustments(final_score, text, stub, extracted_args)
        
        # Ensure score is in valid range
        return max(0.0, min(1.0, final_score))
    
    def _score_pattern_match(self, text: str, stub: Any, match_type: str) -> float:
        """Score based on pattern matching."""
        if match_type == "pattern":
            # Strong pattern match
            return 0.95
        elif match_type == "keyword":
            # Moderate match
            return 0.75
        elif match_type == "action":
            # Action-based match
            return 0.70
        else:
            # Check if any patterns would match
            text_lower = text.lower()
            for pattern_str in stub.patterns:
                if any(word in pattern_str for word in text_lower.split()):
                    return 0.60
            return 0.30
    
    def _score_keyword_overlap(self, text: str, stub: Any) -> float:
        """Score based on keyword overlap."""
        if not stub.keywords:
            return 0.5
        
        text_words = set(text.lower().split())
        stub_keywords = set(stub.keywords)
        
        # Calculate Jaccard similarity
        intersection = text_words & stub_keywords
        union = text_words | stub_keywords
        
        if not union:
            return 0.0
        
        jaccard = len(intersection) / len(union)
        
        # Boost score if important keywords match
        important_keywords = {"create", "delete", "update", "get", "list"}
        important_matches = intersection & important_keywords
        
        if important_matches:
            jaccard = min(1.0, jaccard * 1.2)
        
        return jaccard
    
    def _score_action_match(self, text: str, stub: Any) -> float:
        """Score based on action verb matching."""
        text_lower = text.lower()
        
        # Map methods to action verbs
        method_actions = {
            "POST": ["create", "add", "new", "make", "build", "post"],
            "GET": ["get", "list", "show", "fetch", "retrieve", "find", "view"],
            "PUT": ["update", "edit", "modify", "change", "replace"],
            "PATCH": ["update", "edit", "modify", "patch"],
            "DELETE": ["delete", "remove", "destroy", "clear"],
        }
        
        expected_actions = method_actions.get(stub.method, [])
        
        # Check if any expected action appears in text
        for action in expected_actions:
            if action in text_lower:
                return 0.90
        
        # Check for partial matches
        for action in expected_actions:
            if any(word.startswith(action[:3]) for word in text_lower.split()):
                return 0.60
        
        return 0.30
    
    def _score_parameter_completeness(
        self,
        extracted_args: Dict[str, Any],
        stub: Any
    ) -> float:
        """Score based on parameter completeness."""
        if not stub.input_schema:
            return 1.0  # No parameters needed
        
        properties = stub.input_schema.get("properties", {})
        required = stub.input_schema.get("required", [])
        
        if not properties:
            return 1.0  # No parameters defined
        
        # Check required parameters
        if required:
            required_present = sum(1 for r in required if r in extracted_args)
            required_score = required_present / len(required)
        else:
            required_score = 1.0
        
        # Check optional parameters
        optional = [p for p in properties if p not in required]
        if optional:
            optional_present = sum(1 for o in optional if o in extracted_args)
            optional_score = optional_present / len(optional)
        else:
            optional_score = 1.0
        
        # Weight required parameters more heavily
        return required_score * 0.8 + optional_score * 0.2
    
    def _score_schema_match(
        self,
        extracted_args: Dict[str, Any],
        stub: Any
    ) -> float:
        """Score based on schema validation."""
        if not stub.input_schema or not extracted_args:
            return 0.5
        
        properties = stub.input_schema.get("properties", {})
        valid_count = 0
        total_count = len(extracted_args)
        
        for arg_name, arg_value in extracted_args.items():
            if arg_name in properties:
                prop_schema = properties[arg_name]
                if self._validate_value(arg_value, prop_schema):
                    valid_count += 1
        
        if total_count == 0:
            return 0.5
        
        return valid_count / total_count
    
    def _validate_value(self, value: Any, schema: Dict[str, Any]) -> bool:
        """Validate a value against a schema."""
        expected_type = schema.get("type")
        
        if expected_type == "string":
            if not isinstance(value, str):
                return False
            # Check pattern if present
            if "pattern" in schema:
                import re
                pattern = re.compile(schema["pattern"])
                if not pattern.match(value):
                    return False
            # Check enum if present
            if "enum" in schema and value not in schema["enum"]:
                return False
        elif expected_type == "integer":
            if not isinstance(value, int):
                return False
            # Check range
            if "minimum" in schema and value < schema["minimum"]:
                return False
            if "maximum" in schema and value > schema["maximum"]:
                return False
        elif expected_type == "number":
            if not isinstance(value, (int, float)):
                return False
        elif expected_type == "boolean":
            if not isinstance(value, bool):
                return False
        
        return True
    
    def _apply_adjustments(
        self,
        score: float,
        text: str,
        stub: Any,
        extracted_args: Dict[str, Any]
    ) -> float:
        """Apply final adjustments to confidence score."""
        # Boost if text is very short and specific
        if len(text.split()) <= 3:
            score = min(1.0, score * 1.1)
        
        # Penalty if text is very long and vague
        if len(text.split()) > 20:
            score = score * 0.95
        
        # Boost if all required parameters are present
        if stub.input_schema:
            required = stub.input_schema.get("required", [])
            if required and all(r in extracted_args for r in required):
                score = min(1.0, score * 1.05)
        
        # Penalty if method seems wrong for the action
        text_lower = text.lower()
        if stub.method == "DELETE" and any(
            word in text_lower for word in ["create", "add", "new"]
        ):
            score = score * 0.7
        elif stub.method == "POST" and any(
            word in text_lower for word in ["delete", "remove", "destroy"]
        ):
            score = score * 0.7
        
        return score
    
    def adjust_route_result(self, result: RouteResult) -> RouteResult:
        """
        Adjust confidence in an existing route result.
        
        Args:
            result: Route result to adjust
            
        Returns:
            Adjusted route result
        """
        # Re-evaluate confidence based on all factors
        # This is useful when additional context becomes available
        
        # For now, just ensure decision type matches confidence
        if result.confidence >= 0.88:
            result.decision = "direct"
        elif result.confidence >= 0.70:
            result.decision = "confirm"
        else:
            result.decision = "fallback"
        
        return result


def calculate_confidence(
    text: str,
    stub: Any,
    extracted_args: Dict[str, Any],
    match_type: str = "unknown",
) -> float:
    """
    Convenience function to calculate confidence.
    
    Args:
        text: Input text
        stub: Matched stub
        extracted_args: Extracted arguments
        match_type: Type of match
        
    Returns:
        Confidence score
    """
    scorer = ConfidenceScorer()
    return scorer.score(text, stub, extracted_args, match_type)
