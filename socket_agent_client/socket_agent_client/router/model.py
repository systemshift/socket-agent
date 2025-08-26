"""Optional tiny model integration for enhanced routing."""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from ..exceptions import ModelLoadError
from ..types import RouteResult


class TinyModel:
    """Wrapper for tiny ML models for routing enhancement."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize tiny model.
        
        Args:
            model_path: Path to model file (ONNX, TFLite, etc.)
        """
        self.model_path = model_path
        self.model = None
        self.model_type = None
        self.tokenizer = None
        
        if model_path:
            self._load_model()
    
    def _load_model(self):
        """Load the model based on file extension."""
        if not os.path.exists(self.model_path):
            raise ModelLoadError(f"Model file not found: {self.model_path}")
        
        ext = os.path.splitext(self.model_path)[1].lower()
        
        try:
            if ext == ".onnx":
                self._load_onnx()
            elif ext in [".tflite", ".lite"]:
                self._load_tflite()
            elif ext == ".pt":
                self._load_pytorch()
            elif ext == ".json":
                # Assume it's a simple classifier config
                self._load_json_classifier()
            else:
                raise ModelLoadError(f"Unsupported model format: {ext}")
        except ImportError as e:
            raise ModelLoadError(
                f"Required library not installed for {ext} models: {e}"
            )
    
    def _load_onnx(self):
        """Load ONNX model."""
        try:
            import onnxruntime as ort
            self.model = ort.InferenceSession(self.model_path)
            self.model_type = "onnx"
        except ImportError:
            raise ModelLoadError(
                "ONNX Runtime not installed. Install with: pip install onnxruntime"
            )
    
    def _load_tflite(self):
        """Load TensorFlow Lite model."""
        try:
            import tensorflow as tf
            self.model = tf.lite.Interpreter(model_path=self.model_path)
            self.model.allocate_tensors()
            self.model_type = "tflite"
        except ImportError:
            raise ModelLoadError(
                "TensorFlow not installed. Install with: pip install tensorflow"
            )
    
    def _load_pytorch(self):
        """Load PyTorch model."""
        try:
            import torch
            self.model = torch.jit.load(self.model_path)
            self.model.eval()
            self.model_type = "pytorch"
        except ImportError:
            raise ModelLoadError(
                "PyTorch not installed. Install with: pip install torch"
            )
    
    def _load_json_classifier(self):
        """Load a simple JSON-based classifier."""
        with open(self.model_path, 'r') as f:
            self.model = json.load(f)
        self.model_type = "json"
    
    def rerank(
        self,
        text: str,
        candidates: List[Tuple[Any, float, str]]
    ) -> List[Tuple[Any, float, str]]:
        """
        Rerank candidates using the model.
        
        Args:
            text: Input text
            candidates: List of (stub, confidence, reasoning) tuples
            
        Returns:
            Reranked list of candidates
        """
        if not self.model or not candidates:
            return candidates
        
        if self.model_type == "json":
            return self._rerank_with_json(text, candidates)
        else:
            # Use neural model for reranking
            scores = []
            for stub, conf, reason in candidates:
                score = self._score_with_model(text, stub)
                # Combine with original confidence
                combined_score = conf * 0.6 + score * 0.4
                scores.append((stub, combined_score, reason))
            
            # Sort by combined score
            scores.sort(key=lambda x: x[1], reverse=True)
            return scores
    
    def _rerank_with_json(
        self,
        text: str,
        candidates: List[Tuple[Any, float, str]]
    ) -> List[Tuple[Any, float, str]]:
        """Rerank using JSON classifier rules."""
        # JSON format: {"patterns": [...], "boosts": {...}}
        patterns = self.model.get("patterns", [])
        boosts = self.model.get("boosts", {})
        
        reranked = []
        for stub, conf, reason in candidates:
            boost = 1.0
            
            # Check patterns
            for pattern_rule in patterns:
                import re
                pattern = re.compile(pattern_rule["pattern"], re.IGNORECASE)
                if pattern.search(text):
                    # Apply boost for matching endpoints
                    if stub.name in pattern_rule.get("endpoints", []):
                        boost *= pattern_rule.get("boost", 1.2)
            
            # Check endpoint-specific boosts
            if stub.name in boosts:
                boost *= boosts[stub.name]
            
            # Apply boost to confidence
            new_conf = min(1.0, conf * boost)
            reranked.append((stub, new_conf, reason))
        
        reranked.sort(key=lambda x: x[1], reverse=True)
        return reranked
    
    def _score_with_model(self, text: str, stub: Any) -> float:
        """Score a text-stub pair with the neural model."""
        if self.model_type == "onnx":
            return self._score_with_onnx(text, stub)
        elif self.model_type == "tflite":
            return self._score_with_tflite(text, stub)
        elif self.model_type == "pytorch":
            return self._score_with_pytorch(text, stub)
        else:
            return 0.5
    
    def _score_with_onnx(self, text: str, stub: Any) -> float:
        """Score using ONNX model."""
        # Prepare input
        input_data = self._prepare_input(text, stub)
        
        # Run inference
        input_name = self.model.get_inputs()[0].name
        output_name = self.model.get_outputs()[0].name
        
        result = self.model.run([output_name], {input_name: input_data})
        
        # Extract score (assuming sigmoid output)
        score = float(result[0][0])
        return score
    
    def _score_with_tflite(self, text: str, stub: Any) -> float:
        """Score using TFLite model."""
        # Get input/output details
        input_details = self.model.get_input_details()
        output_details = self.model.get_output_details()
        
        # Prepare input
        input_data = self._prepare_input(text, stub)
        
        # Set input tensor
        self.model.set_tensor(input_details[0]['index'], input_data)
        
        # Run inference
        self.model.invoke()
        
        # Get output
        output_data = self.model.get_tensor(output_details[0]['index'])
        score = float(output_data[0])
        
        return score
    
    def _score_with_pytorch(self, text: str, stub: Any) -> float:
        """Score using PyTorch model."""
        import torch
        
        # Prepare input
        input_data = self._prepare_input(text, stub)
        input_tensor = torch.tensor(input_data, dtype=torch.float32)
        
        # Run inference
        with torch.no_grad():
            output = self.model(input_tensor)
            score = torch.sigmoid(output).item()
        
        return score
    
    def _prepare_input(self, text: str, stub: Any) -> Any:
        """
        Prepare input for the model.
        
        This is a simplified version. Real implementation would need
        proper tokenization and feature extraction.
        """
        # Simple feature extraction
        features = []
        
        # Text length feature
        features.append(len(text.split()))
        
        # Keyword overlap feature
        text_words = set(text.lower().split())
        stub_keywords = set(stub.keywords) if hasattr(stub, 'keywords') else set()
        overlap = len(text_words & stub_keywords)
        features.append(overlap)
        
        # Method match feature
        method_map = {
            "POST": ["create", "add", "new"],
            "GET": ["get", "list", "show"],
            "PUT": ["update", "edit"],
            "DELETE": ["delete", "remove"],
        }
        method_score = 0
        if hasattr(stub, 'method'):
            expected_words = method_map.get(stub.method, [])
            for word in expected_words:
                if word in text.lower():
                    method_score = 1
                    break
        features.append(method_score)
        
        # Pad or truncate to expected size (example: 10 features)
        while len(features) < 10:
            features.append(0)
        features = features[:10]
        
        import numpy as np
        return np.array([features], dtype=np.float32)
    
    def extract_slots(self, text: str, stub: Any) -> Dict[str, Any]:
        """
        Extract parameter slots using the model.
        
        This is a placeholder for slot-filling models.
        """
        # For now, return empty dict
        # A real implementation would use a sequence labeling model
        return {}


class ModelBooster:
    """Boosts routing decisions with optional model."""
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize model booster.
        
        Args:
            model_path: Optional path to model
        """
        self.model = None
        if model_path:
            try:
                self.model = TinyModel(model_path)
            except ModelLoadError as e:
                # Log warning but don't fail
                print(f"Warning: Could not load model: {e}")
    
    def boost(
        self,
        text: str,
        route_result: RouteResult,
        candidates: Optional[List[Tuple[Any, float, str]]] = None
    ) -> RouteResult:
        """
        Boost routing result with model.
        
        Args:
            text: Input text
            route_result: Initial routing result
            candidates: Optional list of candidates
            
        Returns:
            Enhanced route result
        """
        if not self.model or not candidates:
            return route_result
        
        # Rerank candidates
        reranked = self.model.rerank(text, candidates)
        
        if reranked:
            # Update result with top candidate
            best_stub, confidence, reasoning = reranked[0]
            route_result.endpoint = best_stub.name
            route_result.method = best_stub.method
            route_result.path = best_stub.path
            route_result.confidence = confidence
            
            # Update decision based on new confidence
            if confidence >= 0.88:
                route_result.decision = "direct"
            elif confidence >= 0.70:
                route_result.decision = "confirm"
            else:
                route_result.decision = "fallback"
        
        return route_result


def boost_with_model(
    model_path: str,
    text: str,
    candidates: List[Tuple[Any, float, str]],
    stub_store: Any
) -> Tuple[str, Dict[str, Any], float]:
    """
    Convenience function to boost routing with a model.
    
    Args:
        model_path: Path to model
        text: Input text
        candidates: Initial candidates
        stub_store: Stub store
        
    Returns:
        Tuple of (endpoint, args, confidence)
    """
    try:
        model = TinyModel(model_path)
        reranked = model.rerank(text, candidates)
        
        if reranked:
            best_stub, confidence, _ = reranked[0]
            # Extract slots if model supports it
            args = model.extract_slots(text, best_stub)
            return best_stub.name, args, confidence
    except Exception:
        # Fallback to best candidate
        if candidates:
            stub, conf, _ = candidates[0]
            return stub.name, {}, conf
    
    return "unknown", {}, 0.0
