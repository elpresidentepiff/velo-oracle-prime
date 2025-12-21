"""
VÉLØ V12 Helper Functions

Utilities for safe data access across dict/object types.

Author: VELO Team
Version: 1.0 (Phase 1.1)
Date: December 21, 2025
"""

from typing import Any, Optional


def pick(obj: Any, key: str, default: Any = None) -> Any:
    """
    Safely extract a value from either a dict or an object.
    
    Handles both dictionary access (obj[key]) and attribute access (obj.key).
    This is the SINGLE access pattern for OpponentProfile and similar types.
    
    Args:
        obj: Dictionary or object to extract from
        key: Key/attribute name
        default: Default value if key not found
        
    Returns:
        Value if found, else default
        
    Examples:
        >>> profile_dict = {'runner_id': 'r1', 'odds': 2.5}
        >>> pick(profile_dict, 'runner_id')
        'r1'
        
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class Profile:
        ...     runner_id: str
        ...     odds: float
        >>> profile_obj = Profile(runner_id='r1', odds=2.5)
        >>> pick(profile_obj, 'runner_id')
        'r1'
        
        >>> pick(profile_dict, 'missing_key', 'default_value')
        'default_value'
    """
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def pick_nested(obj: Any, path: str, default: Any = None, separator: str = '.') -> Any:
    """
    Safely extract a nested value using dot notation.
    
    Args:
        obj: Dictionary or object to extract from
        path: Dot-separated path (e.g., 'evidence.odds')
        default: Default value if path not found
        separator: Path separator (default '.')
        
    Returns:
        Value if found, else default
        
    Examples:
        >>> data = {'evidence': {'odds': 2.5, 'trainer': 'Smith'}}
        >>> pick_nested(data, 'evidence.odds')
        2.5
        
        >>> pick_nested(data, 'evidence.missing', 0.0)
        0.0
    """
    keys = path.split(separator)
    current = obj
    
    for key in keys:
        if current is None:
            return default
        current = pick(current, key, None)
    
    return current if current is not None else default


def ensure_dict(obj: Any) -> dict:
    """
    Convert object to dict if it has a to_dict() method, otherwise return as-is.
    
    Args:
        obj: Object to convert
        
    Returns:
        Dictionary representation
    """
    if hasattr(obj, 'to_dict') and callable(obj.to_dict):
        return obj.to_dict()
    elif isinstance(obj, dict):
        return obj
    else:
        # Try to convert using __dict__
        return getattr(obj, '__dict__', {})


if __name__ == "__main__":
    # Test examples
    from dataclasses import dataclass
    
    @dataclass
    class TestProfile:
        runner_id: str
        odds: float
        evidence: dict
    
    # Test dict access
    profile_dict = {
        'runner_id': 'r1',
        'odds': 2.5,
        'evidence': {'trainer': 'Smith'}
    }
    
    assert pick(profile_dict, 'runner_id') == 'r1'
    assert pick(profile_dict, 'odds') == 2.5
    assert pick(profile_dict, 'missing', 'default') == 'default'
    assert pick_nested(profile_dict, 'evidence.trainer') == 'Smith'
    
    # Test object access
    profile_obj = TestProfile(
        runner_id='r2',
        odds=3.5,
        evidence={'trainer': 'Jones'}
    )
    
    assert pick(profile_obj, 'runner_id') == 'r2'
    assert pick(profile_obj, 'odds') == 3.5
    assert pick(profile_obj, 'missing', 'default') == 'default'
    assert pick_nested(profile_obj, 'evidence.trainer') == 'Jones'
    
    print("✅ All pick() helper tests passed")
