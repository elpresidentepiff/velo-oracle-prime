#!/usr/bin/env python3
"""
Complete cache integration for FeatureBuilder.
Updates all extractors and FeatureBuilder to use FeatureCache.
"""

def update_builder():
    """Update builder.py with full cache integration."""
    
    path = "/home/ubuntu/velo-oracle/src/features/builder.py"
    
    with open(path, 'r') as f:
        content = f.read()
    
    # Update FeatureBuilder.__init__
    old_fb_init = '''    def __init__(self, config: Optional[FeatureBuilderConfig] = None):
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
    
    new_fb_init = '''    def __init__(self, config: Optional[FeatureBuilderConfig] = None, cache=None):
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
    
    if old_fb_init in content:
        content = content.replace(old_fb_init, new_fb_init)
        print("✅ Updated FeatureBuilder.__init__")
    else:
        print("⚠️  FeatureBuilder.__init__ not found or already updated")
    
    # Update extractor __init__ methods
    extractors = {
        'FormExtractor': 'FormExtractor',
        'ClassExtractor': 'ClassExtractor',
        'DistanceExtractor': 'DistanceExtractor',
        'GoingExtractor': 'GoingExtractor',
        'CourseExtractor': 'CourseExtractor',
        'TrainerExtractor': 'TrainerExtractor',
        'JockeyExtractor': 'JockeyExtractor',
    }
    
    for name in extractors:
        old_init = f'''    def __init__(self):
        super().__init__("{name}")'''
        new_init = f'''    def __init__(self, cache=None):
        super().__init__("{name}", cache=cache)'''
        
        if old_init in content:
            content = content.replace(old_init, new_init)
            print(f"✅ Updated {name}.__init__")
    
    # Write back
    with open(path, 'w') as f:
        f.write(content)
    
    print("\n✅ Cache integration complete!")

if __name__ == '__main__':
    update_builder()

