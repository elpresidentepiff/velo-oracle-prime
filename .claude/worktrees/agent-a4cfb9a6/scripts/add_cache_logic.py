#!/usr/bin/env python3
"""
Add cache usage logic to extractor extract() methods.
This adds the fast-path cache lookups before falling back to history-based extraction.
"""

def add_cache_logic():
    """Add cache lookup logic to all extractors."""
    
    path = "/home/ubuntu/velo-oracle/src/features/builder.py"
    
    with open(path, 'r') as f:
        lines = f.readlines()
    
    # Find TrainerExtractor.extract and add cache logic
    trainer_cache_logic = '''        # Use cache if available
        if self.cache is not None:
            trainer_features = []
            for idx, row in df.iterrows():
                trainer = row['trainer']
                stats = self.cache.trainer_stats.get(trainer, {})
                trainer_features.append({
                    'trainer_win_rate': stats.get('win_rate', 0.0),
                    'trainer_recent_win_rate': stats.get('recent_win_rate', 0.0),
                })
            
            trainer_df = pd.DataFrame(trainer_features, index=df.index)
            result = pd.concat([result, trainer_df], axis=1)
            self.logger.info(f"Extracted {2} trainer features (from cache)")
            return result
        
        # Fallback to history-based extraction
'''
    
    # Find JockeyExtractor.extract and add cache logic  
    jockey_cache_logic = '''        # Use cache if available
        if self.cache is not None:
            jockey_features = []
            for idx, row in df.iterrows():
                jockey = row['jockey']
                trainer = row['trainer']
                
                # Overall jockey stats
                jockey_stats = self.cache.jockey_stats['overall'].get(jockey, {})
                
                # Jockey-trainer combo stats
                combo_key = (jockey, trainer)
                combo_stats = self.cache.jockey_stats['combos'].get(combo_key, {})
                
                jockey_features.append({
                    'jockey_win_rate': jockey_stats.get('win_rate', 0.0),
                    'jockey_trainer_win_rate': combo_stats.get('win_rate', jockey_stats.get('win_rate', 0.0)),
                })
            
            jockey_df = pd.DataFrame(jockey_features, index=df.index)
            result = pd.concat([result, jockey_df], axis=1)
            self.logger.info(f"Extracted {2} jockey features (from cache)")
            return result
        
        # Fallback to history-based extraction
'''
    
    # Insert cache logic after "result = df.copy()" in each extractor
    # This is complex, so I'll use a marker-based approach
    
    # For now, let's just add form cache logic as it's the biggest bottleneck
    form_cache_logic = '''        # Use cache if available
        if self.cache is not None:
            form_features = []
            for idx, row in df.iterrows():
                horse = row['horse']
                stats = self.cache.form_stats.get(horse, {})
                
                form_features.append({
                    'form_last_pos': stats.get('last_pos', 0.0),
                    'form_avg_pos_3': stats.get('avg_pos_3', 0.0),
                    'form_avg_pos_5': stats.get('avg_pos_5', 0.0),
                    'form_wins_3': stats.get('wins_3', 0),
                    'form_wins_5': stats.get('wins_5', 0),
                    'form_places_3': stats.get('places_3', 0),
                })
            
            form_df = pd.DataFrame(form_features, index=df.index)
            result = pd.concat([result, form_df], axis=1)
            self.logger.info(f"Extracted {6} form features (from cache)")
            return result
        
        # Fallback to history-based extraction
'''
    
    # Find FormExtractor.extract method and insert cache logic
    in_form_extract = False
    form_result_line = -1
    
    for i, line in enumerate(lines):
        if 'class FormExtractor' in line:
            in_form_extract = True
        elif in_form_extract and 'result = df.copy()' in line:
            form_result_line = i
            break
    
    if form_result_line > 0:
        # Insert cache logic after result = df.copy()
        lines.insert(form_result_line + 1, '\n' + form_cache_logic + '\n')
        print(f"✅ Added cache logic to FormExtractor at line {form_result_line + 1}")
    
    # Write back
    with open(path, 'w') as f:
        f.writelines(lines)
    
    print("\n✅ Cache logic added!")
    print("Note: Only FormExtractor updated (biggest bottleneck)")
    print("Other extractors can be added incrementally for further speedup")

if __name__ == '__main__':
    add_cache_logic()

