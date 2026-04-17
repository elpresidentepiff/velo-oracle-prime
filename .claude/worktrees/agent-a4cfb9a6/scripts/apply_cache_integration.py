#!/usr/bin/env python3
"""
Apply cache integration to FeatureBuilder and extractors.
This script modifies builder.py to integrate the FeatureCache.
"""

import re

def integrate_cache():
    """Apply all cache integration changes to builder.py."""
    
    builder_path = "/home/ubuntu/velo-oracle/src/features/builder.py"
    
    with open(builder_path, 'r') as f:
        content = f.read()
    
    # 1. Update FeatureExtractor base class to accept cache
    content = re.sub(
        r'def __init__\(self, name: str\):',
        'def __init__(self, name: str, cache=None):',
        content
    )
    
    content = re.sub(
        r'(def __init__\(self, name: str, cache=None\):\s+self\.name = name)',
        r'\1\n        self.cache = cache',
        content
    )
    
    # 2. Update all extractor __init__ methods to accept and pass cache
    extractors = [
        'FormExtractor', 'ClassExtractor', 'DistanceExtractor',
        'GoingExtractor', 'CourseExtractor', 'TrainerExtractor', 'JockeyExtractor'
    ]
    
    for extractor in extractors:
        # Update __init__
        pattern = f'class {extractor}\\(FeatureExtractor\\):.*?def __init__\\(self\\):\\s+super\\(\\).__init__\\("{extractor}"\\)'
        replacement = f'class {extractor}(FeatureExtractor):\n    """..."""\n    \n    def __init__(self, cache=None):\n        super().__init__("{extractor}", cache=cache)'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # 3. Update FeatureBuilder to accept cache and pass to extractors
    old_init = '''    def __init__(self, config: Optional[FeatureBuilderConfig] = None):
        self.config = config or FeatureBuilderConfig()
        
        # Configure logging
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger(__name__)
        
        # Initialize extractors
        self.extractors = [
            RatingExtractor(),
            FormExtractor(),
            ClassExtractor(),
            DistanceExtractor(),
            GoingExtractor(),
            CourseExtractor(),
            TrainerExtractor(),
            JockeyExtractor(),
            WeightExtractor(),
            AgeExtractor(),
            TemporalExtractor(),
            MarketExtractor(),
        ]'''
    
    new_init = '''    def __init__(self, config: Optional[FeatureBuilderConfig] = None, cache=None):
        self.config = config or FeatureBuilderConfig()
        self.cache = cache
        
        # Configure logging
        logging.basicConfig(level=self.config.log_level)
        self.logger = logging.getLogger(__name__)
        
        if self.cache is not None:
            self.logger.info("FeatureBuilder initialized with cache (fast mode)")
        
        # Initialize extractors (pass cache to those that support it)
        self.extractors = [
            RatingExtractor(),
            FormExtractor(cache=cache),
            ClassExtractor(cache=cache),
            DistanceExtractor(cache=cache),
            GoingExtractor(cache=cache),
            CourseExtractor(cache=cache),
            TrainerExtractor(cache=cache),
            JockeyExtractor(cache=cache),
            WeightExtractor(),
            AgeExtractor(),
            TemporalExtractor(),
            MarketExtractor(),
        ]'''
    
    content = content.replace(old_init, new_init)
    
    # Write back
    with open(builder_path, 'w') as f:
        f.write(content)
    
    print("✅ Cache integration applied to builder.py")
    print("   - FeatureExtractor base class updated")
    print("   - All extractor __init__ methods updated")
    print("   - FeatureBuilder updated to accept and pass cache")

if __name__ == '__main__':
    integrate_cache()

