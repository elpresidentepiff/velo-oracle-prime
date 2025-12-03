"""
VÉLØ Oracle - Tactical Report Generator
Generates beautiful tactical reports matching the Kempton 15:57 format
"""
from typing import Dict, List, Optional
from datetime import datetime


class TacticalReportFormatter:
    """Formats race analysis into tactical reports"""
    
    @staticmethod
    def generate_report(race_data: Dict, analysis: Dict) -> str:
        """Generate full tactical report"""
        
        # Header
        course = race_data.get('course', 'UNKNOWN').upper()
        race_time = race_data.get('race_time', '00:00')
        race_id = race_data.get('race_id', 'UNKNOWN')
        race_class = race_data.get('race_class', 'UNKNOWN')
        
        report = f"""VÉLØ ORACLE TACTICAL REPORT: {course} {race_time}

RACE ID: {race_id}
THEME: "{analysis.get('theme', 'The Battle Begins')}"

1. THE FIELD & SIGNAL STRENGTH

"""
        
        # Field Analysis
        for runner_analysis in analysis.get('field_analysis', []):
            report += TacticalReportFormatter.format_runner_analysis(runner_analysis)
            report += "\n"
        
        # Tactical Play
        report += f"""
2. THE TACTICAL PLAY ({course} ATTACK)

The market will likely favor {analysis.get('market_favorite', 'the favorite')}.
The data suggests {analysis.get('data_suggestion', 'a different outcome')}.

COMMAND:

"""
        
        # Betting Commands
        for cmd in analysis.get('betting_commands', []):
            report += TacticalReportFormatter.format_betting_command(cmd)
            report += "\n"
        
        # Forecast
        forecast_selections = analysis.get('forecast', [])
        if forecast_selections:
            forecast_str = " - ".join([str(s) for s in forecast_selections])
            report += f"\nFORECAST (Box): {forecast_str}.\n"
            report += f"Why: {analysis.get('forecast_reason', 'Cover the key contenders')}.\n"
        
        # Final verdict
        report += f"\n{analysis.get('final_verdict', 'Execute.')}\n"
        
        return report
    
    @staticmethod
    def format_runner_analysis(runner: Dict) -> str:
        """Format individual runner analysis"""
        name = runner.get('name', 'UNKNOWN').upper()
        number = runner.get('number', 0)
        signal = runner.get('signal', 'CONTENDER')
        
        analysis_text = f"""{name} (#{number})

Signal: {signal}.

Logic:
"""
        
        # Rating
        rating = runner.get('rating', 0)
        if rating:
            analysis_text += f"Rating: RPR {rating}.\n"
        
        # Form
        form = runner.get('form', '')
        if form:
            analysis_text += f"Form: {form}.\n"
        
        # Key factors
        key_factors = runner.get('key_factors', [])
        for factor in key_factors:
            analysis_text += f"{factor}\n"
        
        # Verdict
        verdict = runner.get('verdict', 'CONTENDER')
        analysis_text += f"\nVerdict: {verdict}.\n"
        
        return analysis_text
    
    @staticmethod
    def format_betting_command(cmd: Dict) -> str:
        """Format betting command"""
        bet_type = cmd.get('type', 'WIN').upper()
        selection = cmd.get('selection', 'UNKNOWN').upper()
        number = cmd.get('number', 0)
        stake_type = cmd.get('stake_type', 'Standard')
        reason = cmd.get('reason', 'Value identified')
        
        if number:
            selection_str = f"{selection} (#{number})"
        else:
            selection_str = selection
        
        command_text = f"{bet_type}: {selection_str}. ({stake_type}).\n"
        command_text += f"Why: {reason}.\n"
        
        return command_text


class TacticalAnalyzer:
    """Analyzes race and generates tactical insights"""
    
    @staticmethod
    def analyze_race(race_data: Dict) -> Dict:
        """Perform tactical analysis"""
        runners = race_data.get('runners', [])
        
        # Identify key horses
        class_act = TacticalAnalyzer.find_class_act(runners)
        danger = TacticalAnalyzer.find_danger_horse(runners)
        specialist = TacticalAnalyzer.find_course_specialist(runners)
        favorite = TacticalAnalyzer.find_favorite(runners)
        
        # Build analysis
        analysis = {
            'theme': TacticalAnalyzer.generate_theme(class_act, danger, specialist),
            'field_analysis': [],
            'betting_commands': [],
            'forecast': [],
            'market_favorite': favorite.get('name', 'the favorite') if favorite else 'the favorite',
            'data_suggestion': ''
        }
        
        # Analyze class act
        if class_act:
            class_analysis = {
                'name': class_act['name'],
                'number': class_act.get('number', 0),
                'signal': 'THE CLASS ACT (Shield)',
                'rating': class_act.get('rating', 0),
                'form': class_act.get('recent_form', ''),
                'key_factors': TacticalAnalyzer.get_class_factors(class_act),
                'verdict': 'THE WINNER'
            }
            analysis['field_analysis'].append(class_analysis)
            
            # Betting command
            analysis['betting_commands'].append({
                'type': 'WIN',
                'selection': class_act['name'],
                'number': class_act.get('number', 0),
                'stake_type': 'Anchor',
                'reason': TacticalAnalyzer.get_class_reason(class_act)
            })
            
            analysis['forecast'].append(class_act.get('number', 0))
        
        # Analyze danger horse
        if danger:
            danger_analysis = {
                'name': danger['name'],
                'number': danger.get('number', 0),
                'signal': 'THE SWORD (Danger)',
                'rating': danger.get('rating', 0),
                'form': danger.get('recent_form', ''),
                'key_factors': TacticalAnalyzer.get_danger_factors(danger),
                'verdict': 'VALUE THREAT'
            }
            analysis['field_analysis'].append(danger_analysis)
            
            # Betting command
            analysis['betting_commands'].append({
                'type': 'EACH WAY / SAVER',
                'selection': danger['name'],
                'number': danger.get('number', 0),
                'stake_type': 'Saver',
                'reason': TacticalAnalyzer.get_danger_reason(danger)
            })
            
            analysis['forecast'].append(danger.get('number', 0))
        
        # Analyze course specialist
        if specialist:
            specialist_analysis = {
                'name': specialist['name'],
                'number': specialist.get('number', 0),
                'signal': 'THE COURSE SPECIALIST',
                'rating': specialist.get('rating', 0),
                'form': specialist.get('recent_form', ''),
                'key_factors': TacticalAnalyzer.get_specialist_factors(specialist),
                'verdict': 'THE SAFE EACH-WAY'
            }
            analysis['field_analysis'].append(specialist_analysis)
            
            # Betting command (if not already in forecast)
            if specialist.get('number', 0) not in analysis['forecast']:
                analysis['betting_commands'].append({
                    'type': 'EACH WAY',
                    'selection': specialist['name'],
                    'number': specialist.get('number', 0),
                    'stake_type': 'Safe EW',
                    'reason': TacticalAnalyzer.get_specialist_reason(specialist)
                })
                
                analysis['forecast'].append(specialist.get('number', 0))
        
        # Set data suggestion
        if class_act:
            analysis['data_suggestion'] = f"{class_act['name']} is the 'Class' horse"
        
        # Forecast reason
        forecast_names = []
        if class_act:
            forecast_names.append(f"Class (#{class_act.get('number', 0)})")
        if specialist:
            forecast_names.append(f"Course Form (#{specialist.get('number', 0)})")
        if danger:
            forecast_names.append(f"Class Dropper (#{danger.get('number', 0)})")
        
        analysis['forecast_reason'] = "Cover the " + ", ".join(forecast_names)
        
        # Final verdict
        if class_act:
            analysis['final_verdict'] = f"{class_act['name']} is the 'Now' horse. Execute."
        else:
            analysis['final_verdict'] = "Execute."
        
        return analysis
    
    @staticmethod
    def find_class_act(runners: List[Dict]) -> Optional[Dict]:
        """Find the class horse"""
        # Highest rating with recent form
        class_horses = [r for r in runners if r.get('rating', 0) > 0]
        if class_horses:
            # Sort by rating
            class_horses.sort(key=lambda x: x.get('rating', 0), reverse=True)
            # Check if top-rated has decent recent form
            top = class_horses[0]
            recent_form = top.get('recent_form', '')
            if recent_form:
                # If last run was top 3, it's the class act
                if recent_form[0] in ['1', '2', '3']:
                    return top
            # Otherwise, check second-highest
            if len(class_horses) > 1:
                return class_horses[1]
            return top
        return None
    
    @staticmethod
    def find_danger_horse(runners: List[Dict]) -> Optional[Dict]:
        """Find the danger horse (class dropper)"""
        # Look for class drop
        danger_horses = [r for r in runners if r.get('class_change', 0) < 0]
        if danger_horses:
            # Highest rated class dropper
            return max(danger_horses, key=lambda x: x.get('rating', 0))
        return None
    
    @staticmethod
    def find_course_specialist(runners: List[Dict]) -> Optional[Dict]:
        """Find the course specialist"""
        # Best course record
        specialists = [r for r in runners if r.get('course_wins', 0) > 0]
        if specialists:
            # Sort by course win percentage
            specialists.sort(
                key=lambda x: x.get('course_wins', 0) / max(x.get('course_runs', 1), 1),
                reverse=True
            )
            return specialists[0]
        return None
    
    @staticmethod
    def find_favorite(runners: List[Dict]) -> Optional[Dict]:
        """Find the market favorite"""
        if runners:
            return min(runners, key=lambda x: x.get('win_odds', 999))
        return None
    
    @staticmethod
    def generate_theme(class_act, danger, specialist) -> str:
        """Generate race theme"""
        if class_act and danger:
            return f"The Class Act vs. The {danger.get('name', 'Challenger')}"
        elif class_act and specialist:
            return "The Class Dropper vs. The Speed Machine"
        elif class_act:
            return "Class Tells"
        elif danger:
            return "The Upset Special"
        else:
            return "Open Contest"
    
    @staticmethod
    def get_class_factors(horse: Dict) -> List[str]:
        """Get class factors"""
        factors = []
        
        rating = horse.get('rating', 0)
        if rating:
            factors.append(f"Rating: RPR {rating}.")
        
        form = horse.get('recent_form', '')
        if form:
            factors.append(f"Trajectory: {form}. Recent return to form.")
        
        factors.append("The Key: Has class advantage.")
        
        return factors
    
    @staticmethod
    def get_danger_factors(horse: Dict) -> List[str]:
        """Get danger factors"""
        factors = []
        
        rating = horse.get('rating', 0)
        if rating:
            factors.append(f"Rating: RPR {rating}.")
        
        form = horse.get('recent_form', '')
        if form:
            factors.append(f"Form: {form}. Looks bad on paper, BUT...")
        
        class_change = horse.get('class_change', 0)
        if class_change < 0:
            factors.append(f"Class Drop: Dropping {abs(class_change)} classes. Massive drop.")
        
        trainer = horse.get('trainer', '')
        if trainer:
            factors.append(f"Trainer: {trainer}.")
        
        return factors
    
    @staticmethod
    def get_specialist_factors(horse: Dict) -> List[str]:
        """Get specialist factors"""
        factors = []
        
        speed = horse.get('speed_figure', 0)
        if speed:
            factors.append(f"Speed: TS {speed}.")
        
        course_wins = horse.get('course_wins', 0)
        course_runs = horse.get('course_runs', 1)
        if course_wins > 0:
            win_pct = (course_wins / course_runs) * 100
            factors.append(f"Course Stats: {course_wins} wins from {course_runs} runs ({win_pct:.0f}%).")
        
        form = horse.get('recent_form', '')
        if form and form[0] == '1':
            factors.append("Form: Won last time out.")
        
        return factors
    
    @staticmethod
    def get_class_reason(horse: Dict) -> str:
        """Get class reason"""
        return "Unexposed profile. Class advantage"
    
    @staticmethod
    def get_danger_reason(horse: Dict) -> str:
        """Get danger reason"""
        rating = horse.get('rating', 0)
        return f"RPR {rating}. If wakes up in this lower grade, wins"
    
    @staticmethod
    def get_specialist_reason(horse: Dict) -> str:
        """Get specialist reason"""
        course_wins = horse.get('course_wins', 0)
        return f"Course form ({course_wins} wins here)"


def generate_tactical_report(race_data: Dict) -> str:
    """Main function to generate tactical report"""
    # Analyze race
    analysis = TacticalAnalyzer.analyze_race(race_data)
    
    # Format report
    report = TacticalReportFormatter.generate_report(race_data, analysis)
    
    return report


# Example usage
if __name__ == "__main__":
    # Sample race data (Kempton 15:57)
    kempton_race = {
        'race_id': 'KEMP_1557_HCP',
        'course': 'KEMPTON',
        'race_time': '15:57',
        'race_class': '3',
        'runners': [
            {
                'id': 1,
                'name': 'UNITED APPROACH',
                'number': 1,
                'win_odds': 3.5,
                'place_odds': 1.8,
                'win_probability': 0.28,
                'rating': 94,
                'recent_form': '5-3802',
                'class_change': 0,
                'course_wins': 0,
                'course_runs': 2,
                'trainer': 'Jamie Osborne'
            },
            {
                'id': 3,
                'name': 'SILVER SAMURAI',
                'number': 3,
                'win_odds': 5.0,
                'place_odds': 2.2,
                'win_probability': 0.20,
                'rating': 96,
                'recent_form': '275769',
                'class_change': -2,  # Class dropper
                'course_wins': 0,
                'course_runs': 1,
                'trainer': 'Marco Botti'
            },
            {
                'id': 8,
                'name': 'HOW IMPRESSIVE',
                'number': 8,
                'win_odds': 4.0,
                'place_odds': 1.9,
                'win_probability': 0.25,
                'rating': 88,
                'recent_form': '1',
                'class_change': 0,
                'course_wins': 2,
                'course_runs': 3,
                'speed_figure': 82
            },
            {
                'id': 5,
                'name': 'MYTHICAL COMPOSER',
                'number': 5,
                'win_odds': 6.0,
                'place_odds': 2.5,
                'win_probability': 0.16,
                'rating': 85,
                'recent_form': '456',
                'class_change': 0,
                'course_wins': 0,
                'course_runs': 1,
                'speed_figure': 54,
                'trainer': 'Clive Cox',
                'jockey': 'Rossa Ryan'
            }
        ]
    }
    
    # Generate report
    report = generate_tactical_report(kempton_race)
    
    print(report)
