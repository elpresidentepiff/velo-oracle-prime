"""
VÉLØ v10 - Command Line Interface
Unified CLI for all Oracle operations using Typer

Usage:
    python -m src.cli analyze --date 2024-11-01 --course Ascot --time 14:30
    python -m src.cli backtest --from 2024-01-01 --to 2024-10-31
    python -m src.cli calibrate --races 1000
"""

import typer
from typing import Optional
from datetime import datetime
import sys

from .core.settings import settings
from .core import log
from .integrations import RacingClient, BetfairClient
from .models import BenterModel, OverlaySelector
from .modules.contracts import Overlay

app = typer.Typer(
    name="velo",
    help="VÉLØ v10 - Oracle of Odds CLI",
    add_completion=False
)


@app.command()
def analyze(
    date: str = typer.Option(..., "--date", "-d", help="Race date (YYYY-MM-DD)"),
    course: str = typer.Option(..., "--course", "-c", help="Course name"),
    time: str = typer.Option(..., "--time", "-t", help="Race time (HH:MM)"),
    alpha: Optional[float] = typer.Option(None, "--alpha", help="Benter alpha weight"),
    beta: Optional[float] = typer.Option(None, "--beta", help="Benter beta weight"),
    min_edge: Optional[float] = typer.Option(None, "--min-edge", help="Minimum edge threshold"),
    max_bets: int = typer.Option(1, "--max-bets", help="Maximum bets per race"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file (JSON)"),
):
    """
    Analyze a race and identify overlays
    
    Example:
        python -m src.cli analyze -d 2024-11-01 -c Ascot -t 14:30
    """
    # Initialize logging
    log.setup_logging("config/logging.json")
    
    with log.EventLogger("analyze_race", date=date, course=course, time=time):
        typer.echo(f"🏇 Analyzing {course} {time} on {date}...")
        
        try:
            # Initialize clients
            racing = RacingClient()
            betfair = BetfairClient()
            
            # Get racecard
            typer.echo(f"📋 Fetching racecard...")
            racecard = racing.get_racecard(date, course, time)
            
            if not racecard:
                typer.echo(f"❌ Could not fetch racecard for {course} {time}", err=True)
                raise typer.Exit(1)
            
            typer.echo(f"✅ Racecard loaded: {racecard.num_runners} runners")
            
            # Get odds
            typer.echo(f"💰 Fetching odds...")
            # Note: In production, we'd get market_id from racecard
            # For now, using placeholder
            odds_book = {}  # betfair.get_market_odds(market_id)
            
            if not odds_book:
                typer.echo(f"⚠️  No odds available, using placeholder", err=True)
                # Create placeholder odds for demonstration
                for runner in racecard.runners:
                    from .modules.contracts import Odds
                    odds_book[runner.name] = Odds(win=5.0)  # Placeholder
            
            # Initialize models
            benter = BenterModel(alpha=alpha, beta=beta)
            selector = OverlaySelector(min_edge=min_edge)
            
            # Estimate probabilities
            typer.echo(f"🧮 Running Benter model...")
            probabilities = benter.estimate_race(racecard, odds_book)
            
            # Find overlays
            typer.echo(f"🔍 Searching for overlays...")
            overlays = selector.find_overlays(probabilities, odds_book, racecard)
            
            if not overlays:
                typer.echo(f"❌ No overlays found")
                return
            
            # Select best
            best_overlays = selector.select_best(overlays, max_bets=max_bets)
            
            # Display results
            typer.echo(f"\n{'='*60}")
            typer.echo(f"🎯 OVERLAYS FOUND: {len(best_overlays)}")
            typer.echo(f"{'='*60}\n")
            
            for i, overlay in enumerate(best_overlays, 1):
                typer.echo(f"{i}. {overlay.runner}")
                typer.echo(f"   Odds: {overlay.odds:.2f}")
                typer.echo(f"   Model Prob: {overlay.p_model:.3f} ({overlay.p_model*100:.1f}%)")
                typer.echo(f"   Market Prob: {overlay.p_market:.3f} ({overlay.p_market*100:.1f}%)")
                typer.echo(f"   Edge: {overlay.edge:.3f} ({overlay.edge*100:.1f}%)")
                typer.echo(f"   ROI: {overlay.roi():.1f}%")
                typer.echo(f"   Stake: {overlay.stake_fraction:.3f} (Kelly fraction)")
                typer.echo()
            
            # Save to file if requested
            if output:
                import json
                output_data = {
                    "race": {
                        "date": date,
                        "course": course,
                        "time": time,
                        "runners": racecard.num_runners
                    },
                    "overlays": [
                        {
                            "runner": o.runner,
                            "odds": o.odds,
                            "p_model": o.p_model,
                            "p_market": o.p_market,
                            "edge": o.edge,
                            "roi": o.roi(),
                            "stake_fraction": o.stake_fraction
                        }
                        for o in best_overlays
                    ]
                }
                
                with open(output, 'w') as f:
                    json.dump(output_data, f, indent=2)
                
                typer.echo(f"💾 Results saved to {output}")
            
        except Exception as e:
            typer.echo(f"❌ Error: {e}", err=True)
            raise typer.Exit(1)


@app.command()
def backtest(
    from_date: str = typer.Option(..., "--from", help="Start date (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="End date (YYYY-MM-DD)"),
    course: Optional[str] = typer.Option(None, "--course", help="Filter by course"),
    output: Optional[str] = typer.Option("backtest_results.json", "--output", "-o", help="Output file"),
):
    """
    Backtest the Oracle on historical data
    
    Example:
        python -m src.cli backtest --from 2024-01-01 --to 2024-10-31
    """
    log.setup_logging("config/logging.json")
    
    typer.echo(f"📊 Backtesting from {from_date} to {to_date}...")
    typer.echo(f"⚠️  Backtest functionality not yet implemented")
    typer.echo(f"   This will be added in Phase 5")


@app.command()
def calibrate(
    races: int = typer.Option(1000, "--races", help="Number of historical races to use"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file for calibrated weights"),
):
    """
    Calibrate Benter model weights (α, β) on historical data
    
    Example:
        python -m src.cli calibrate --races 1000
    """
    log.setup_logging("config/logging.json")
    
    typer.echo(f"🔧 Calibrating Benter model on {races} races...")
    typer.echo(f"⚠️  Calibration functionality not yet implemented")
    typer.echo(f"   This will be added in Phase 5")


@app.command()
def version():
    """Show VÉLØ version and configuration"""
    typer.echo(f"VÉLØ v10.0 - Oracle of Odds")
    typer.echo(f"Environment: {settings.ENV}")
    typer.echo(f"Debug: {settings.DEBUG}")
    typer.echo(f"")
    typer.echo(f"Configuration:")
    typer.echo(f"  Benter α: {settings.ALPHA}")
    typer.echo(f"  Benter β: {settings.BETA}")
    typer.echo(f"  Kelly fraction: {settings.FRACTIONAL_KELLY}")
    typer.echo(f"  Min edge: {settings.CONFIDENCE_THRESHOLD}")
    typer.echo(f"  Odds range: [{settings.MIN_ODDS}, {settings.MAX_ODDS}]")
    typer.echo(f"")
    typer.echo(f"Integrations:")
    typer.echo(f"  Betfair: {'✅' if settings.has_betfair_credentials() else '❌'}")
    typer.echo(f"  Racing API: {'✅' if settings.has_racing_api_key() else '❌'}")


if __name__ == "__main__":
    app()

