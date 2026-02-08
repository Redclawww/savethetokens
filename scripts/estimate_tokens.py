#!/usr/bin/env python3
"""
Token Estimator - Estimates token counts for content.

Uses tiktoken library when available, falls back to heuristics.
"""

import sys


class TokenEstimator:
    """Estimates token counts for text content."""
    
    # Character-to-token ratios by content type
    RATIOS = {
        "code": 3.5,      # Code is more token-dense
        "prose": 4.0,     # English prose
        "json": 3.0,      # JSON structures
        "markdown": 3.8,  # Markdown with formatting
        "default": 4.0    # Default ratio
    }
    
    def __init__(self, model: str = "cl100k_base"):
        """
        Initialize estimator.
        
        Args:
            model: tiktoken model to use (default: cl100k_base for Claude)
        """
        self.model = model
        self._encoder = None
        self._tiktoken_available = False
        
        try:
            import tiktoken
            self._encoder = tiktoken.get_encoding(model)
            self._tiktoken_available = True
        except ImportError:
            pass
        except Exception:
            pass
    
    def estimate(self, content: str, content_type: str = "default") -> int:
        """
        Estimate token count for content.
        
        Args:
            content: Text content to estimate
            content_type: Type of content (code, prose, json, markdown)
            
        Returns:
            Estimated token count
        """
        if not content:
            return 0
        
        # Use tiktoken if available
        if self._tiktoken_available and self._encoder:
            try:
                return len(self._encoder.encode(content))
            except Exception:
                pass
        
        # Fall back to heuristic
        ratio = self.RATIOS.get(content_type, self.RATIOS["default"])
        return max(1, int(len(content) / ratio))
    
    def estimate_batch(self, items: list[dict]) -> list[dict]:
        """
        Estimate tokens for a batch of items.
        
        Args:
            items: List of dicts with 'content' and optional 'type' keys
            
        Returns:
            Same list with 'tokens' added to each item
        """
        for item in items:
            content = item.get("content", "")
            content_type = item.get("type", "default")
            
            # Map context types to content types
            type_mapping = {
                "file": "code",
                "system": "prose",
                "message": "prose",
                "tool_output": "json",
                "reference": "markdown"
            }
            mapped_type = type_mapping.get(content_type, "default")
            
            item["tokens"] = self.estimate(content, mapped_type)
        
        return items
    
    @property
    def using_tiktoken(self) -> bool:
        """Whether tiktoken is being used for accurate estimates."""
        return self._tiktoken_available


def main():
    """CLI entry point."""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="Estimate token counts")
    parser.add_argument("--text", "-t", help="Text to estimate")
    parser.add_argument("--input", "-f", help="Input JSON file")
    parser.add_argument("--type", default="default", help="Content type")
    
    args = parser.parse_args()
    
    estimator = TokenEstimator()
    
    if args.text:
        tokens = estimator.estimate(args.text, args.type)
        print(json.dumps({
            "text_length": len(args.text),
            "tokens": tokens,
            "using_tiktoken": estimator.using_tiktoken
        }))
    elif args.input:
        with open(args.input) as f:
            data = json.load(f)
        
        if isinstance(data, list):
            items = estimator.estimate_batch(data)
        else:
            items = estimator.estimate_batch(data.get("context_units", [data]))
        
        print(json.dumps(items, indent=2))
    else:
        # Read from stdin
        text = sys.stdin.read()
        tokens = estimator.estimate(text, args.type)
        print(tokens)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
