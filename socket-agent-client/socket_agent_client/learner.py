"""Pattern learning and stub generation for socket-agent clients."""

import re
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from .models import APICall, APIResult, LearnedPattern, Stub


class PatternLearner:
    """Learn patterns from API usage to generate optimized stubs."""
    
    def __init__(self, min_observations: int = 5, min_confidence: float = 0.8):
        """
        Initialize the learner.
        
        Args:
            min_observations: Minimum observations before considering a pattern
            min_confidence: Minimum confidence score for patterns
        """
        self.min_observations = min_observations
        self.min_confidence = min_confidence
        self.observations: List[Tuple[str, APICall, APIResult]] = []
        self.source_url: Optional[str] = None
    
    def observe(self, intent: str, call: APICall, result: APIResult):
        """
        Record an API interaction.
        
        Args:
            intent: User intent or task description
            call: The API call made
            result: The result of the call
        """
        self.observations.append((intent, call, result))
    
    def analyze_patterns(self) -> List[LearnedPattern]:
        """
        Analyze observations to find patterns.
        
        Returns:
            List of learned patterns with confidence scores
        """
        # Group by endpoint
        endpoint_groups = defaultdict(list)
        for intent, call, result in self.observations:
            key = f"{call.method}:{call.path}"
            endpoint_groups[key].append((intent, call, result))
        
        patterns = []
        
        for endpoint_key, group in endpoint_groups.items():
            if len(group) < self.min_observations:
                continue
            
            method, path = endpoint_key.split(':', 1)
            
            # Analyze intents for this endpoint
            intents = [item[0].lower() for item in group]
            intent_pattern = self._find_intent_pattern(intents)
            
            # Calculate success rate
            successes = sum(1 for _, _, result in group if result.status_code < 400)
            success_rate = successes / len(group)
            
            if success_rate < self.min_confidence:
                continue
            
            # Analyze parameter patterns
            param_patterns = self._analyze_parameters(group)
            
            pattern = LearnedPattern(
                intent_pattern=intent_pattern,
                api_pattern={
                    "method": method,
                    "path": path,
                    "extract_params": param_patterns
                },
                confidence=success_rate,
                observations=len(group),
                success_rate=success_rate
            )
            
            patterns.append(pattern)
        
        return sorted(patterns, key=lambda p: p.confidence, reverse=True)
    
    def _find_intent_pattern(self, intents: List[str]) -> str:
        """Find common patterns in intents."""
        if not intents:
            return ".*"
        
        # Find common words
        word_freq = defaultdict(int)
        for intent in intents:
            words = re.findall(r'\w+', intent)
            for word in words:
                word_freq[word] += 1
        
        # Get words that appear in >50% of intents
        threshold = len(intents) * 0.5
        common_words = [word for word, freq in word_freq.items() if freq >= threshold]
        
        if not common_words:
            return ".*"
        
        # Build pattern
        pattern_parts = []
        for word in common_words:
            # Check if it's an action word
            if word in ['create', 'add', 'new', 'make', 'build']:
                pattern_parts.append(f"({word}|create|add|new)")
            elif word in ['list', 'show', 'get', 'fetch', 'display']:
                pattern_parts.append(f"({word}|list|show|get)")
            elif word in ['update', 'edit', 'modify', 'change']:
                pattern_parts.append(f"({word}|update|edit|modify)")
            elif word in ['delete', 'remove', 'destroy']:
                pattern_parts.append(f"({word}|delete|remove)")
            else:
                pattern_parts.append(word)
        
        return ".*" + ".*".join(pattern_parts) + ".*"
    
    def _analyze_parameters(self, group: List[Tuple[str, APICall, APIResult]]) -> Dict[str, str]:
        """Analyze how parameters are extracted from intents."""
        param_patterns = {}
        
        # Collect all parameters used
        all_params = []
        for intent, call, result in group:
            if call.body:
                all_params.append((intent, call.body))
            elif call.params:
                all_params.append((intent, call.params))
        
        if not all_params:
            return param_patterns
        
        # Find common parameter names
        param_names = set()
        for _, params in all_params:
            param_names.update(params.keys())
        
        # For each parameter, try to find extraction pattern
        for param_name in param_names:
            examples = []
            for intent, params in all_params:
                if param_name in params:
                    examples.append((intent, params[param_name]))
            
            if examples:
                # Simple heuristic: if the parameter value appears in the intent
                extraction_hint = "extract from intent"
                for intent, value in examples[:3]:  # Check first few
                    if isinstance(value, str) and value.lower() in intent.lower():
                        extraction_hint = f"text after action words"
                        break
                
                param_patterns[param_name] = extraction_hint
        
        return param_patterns
    
    def generate_stub(self, source_url: str) -> Stub:
        """
        Generate an optimized stub from learned patterns.
        
        Args:
            source_url: URL of the original descriptor
            
        Returns:
            Stub object
        """
        patterns = self.analyze_patterns()
        
        metadata = {
            "created": datetime.now().isoformat(),
            "total_calls": len(self.observations),
            "unique_intents": len(set(obs[0] for obs in self.observations)),
            "endpoints_used": len(set(f"{obs[1].method}:{obs[1].path}" for obs in self.observations)),
        }
        
        return Stub(
            version="1.0",
            source=source_url,
            learned_patterns=patterns,
            metadata=metadata
        )
    
    def clear(self):
        """Clear all observations."""
        self.observations.clear()
