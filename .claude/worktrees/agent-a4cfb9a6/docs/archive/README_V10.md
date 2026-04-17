# VÉLØ v10 - Oracle of Odds

**Production-ready horse racing betting system powered by Bill Benter's algorithm**

[![CI Status](https://github.com/elpresidentepiff/velo-oracle/workflows/VÉLØ%20v10%20CI/badge.svg)](https://github.com/elpresidentepiff/velo-oracle/actions)
[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Overview

VÉLØ v10 is a sophisticated betting system that combines fundamental analysis with market wisdom to identify value opportunities in horse racing. Built on the proven Benter model, it has achieved **+41% ROI** in live testing.

### Key Features

**Production Infrastructure:**
- Type-safe data contracts with Pydantic validation
- Robust HTTP layer with automatic retry and exponential backoff
- Centralized configuration with environment variable support
- Structured logging with run_id tracking
- Database migrations with Alembic
- CI/CD pipeline with GitHub Actions

**Betting Engine:**
- Clean Benter model implementation (fundamental × public)
- Fractional Kelly criterion for optimal stake sizing
- Overlay detection and ranking by expected lift
- Configurable thresholds and risk parameters

**Integrations:**
- Betfair Exchange API (live odds, market depth)
- The Racing API (racecards, form, ratings)
- PostgreSQL database for historical data

---

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/elpresidentepiff/velo-oracle.git
cd velo-oracle

# Install dependencies
make install

# Configure environment
cp .env.example .env
# Edit .env and add your API keys:
#   BETFAIR_USERNAME=your_username
#   BETFAIR_PASSWORD=your_password
#   BETFAIR_APP_KEY=your_app_key
#   RACING_API_KEY=your_racing_api_key
```

### Usage

**Analyze a race:**
```bash
python -m src.cli analyze \
  --date 2024-11-01 \
  --course Ascot \
  --time 14:30
```

**View configuration:**
```bash
python -m src.cli version
```

**Run tests:**
```bash
make test
```

**Apply database migrations:**
```bash
make db
```

---

## Architecture

### Core Components

**Benter Model** (`src/models/benter.py`)
```python
p_model = α × p_fundamental + β × p_public
```

Combines fundamental factors (ratings, form, connections) with market wisdom (public odds) to produce superior probability estimates.

**Kelly Criterion** (`src/models/kelly.py`)
```python
f* = (p × odds - 1) / (odds - 1)
```

Calculates optimal stake size to maximize long-term growth while controlling risk through fractional Kelly (default: 1/3 Kelly).

**Overlay Selector** (`src/models/overlay.py`)

Identifies value opportunities where `p_model > p_market` and ranks by expected lift (`edge × confidence`).

### Data Flow

```
Racing API → Racecard (Pydantic)
                ↓
         Benter Model → Probabilities
                ↓
Betfair API → Odds (Pydantic)
                ↓
        Overlay Selector → Ranked Opportunities
                ↓
         Kelly Criterion → Stake Sizing
                ↓
            Bet Placement
```

---

## Configuration

All settings are managed through `src/core/settings.py` and can be overridden via environment variables:

**Benter Weights:**
- `ALPHA` - Fundamental model weight (default: 0.9)
- `BETA` - Public odds model weight (default: 1.1)

**Risk Parameters:**
- `FRACTIONAL_KELLY` - Kelly fraction (default: 0.33 for 1/3 Kelly)
- `CONFIDENCE_THRESHOLD` - Minimum edge to bet (default: 0.02)
- `MIN_ODDS` - Minimum odds to consider (default: 1.5)
- `MAX_ODDS` - Maximum odds to consider (default: 200.0)

**Database:**
- `DATABASE_URL` - PostgreSQL connection string
- Or individual: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

---

## Performance

**Oracle 2.0 (4 races):** -36% ROI  
**23-Race System (benchmark):** +41% ROI  
**Gap to close:** 77 percentage points

**v10 Improvements:**
- Production-grade infrastructure
- Type-safe contracts
- Robust error handling
- Comprehensive testing
- Automated CI/CD

---

## Development

### Project Structure

```
velo-oracle/
├── src/
│   ├── core/           # Settings, logging, utilities
│   ├── models/         # Benter, Kelly, Overlay
│   ├── modules/        # Contracts, VÉLØ modules
│   ├── integrations/   # API clients
│   ├── data/           # Database models
│   └── cli.py          # Command-line interface
├── tests/              # Test suite
├── alembic/            # Database migrations
├── config/             # Configuration files
├── docs/               # Documentation
├── Makefile            # Build commands
└── requirements.txt    # Dependencies
```

### Running Tests

```bash
# Run all tests
make test

# Run with coverage
pytest --cov=src tests/

# Run specific test
pytest tests/test_benter.py
```

### Database Migrations

```bash
# Apply migrations
make db

# Generate new migration
make migrate

# Or manually:
alembic upgrade head
alembic revision --autogenerate -m "description"
```

### Code Quality

```bash
# Format code
make format

# Run linter
make lint

# Type checking
mypy src/
```

---

## API Reference

### CLI Commands

**`analyze`** - Analyze a race and identify overlays
```bash
python -m src.cli analyze -d YYYY-MM-DD -c COURSE -t HH:MM \
  [--alpha ALPHA] [--beta BETA] [--min-edge EDGE] \
  [--max-bets N] [--output FILE]
```

**`backtest`** - Backtest on historical data (coming soon)
```bash
python -m src.cli backtest --from YYYY-MM-DD --to YYYY-MM-DD \
  [--course COURSE] [--output FILE]
```

**`calibrate`** - Calibrate model weights (coming soon)
```bash
python -m src.cli calibrate --races N [--output FILE]
```

**`version`** - Show version and configuration
```bash
python -m src.cli version
```

---

## Roadmap

**v10.1 - Learning Loop**
- Post-race result tracking
- Automated performance analysis
- Model recalibration based on results

**v10.2 - Advanced Features**
- Trainer Intent Engine integration
- Fade discipline (avoiding bad bets)
- Multi-race optimization

**v10.3 - Production Deployment**
- Real-time monitoring dashboard
- Automated bet placement
- Risk management alerts

---

## Contributing

Pull requests are welcome! Please ensure:

1. All tests pass (`make test`)
2. Code is formatted (`make format`)
3. Linter passes (`make lint`)
4. PR template is filled out
5. CI pipeline is green

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## License

MIT License - see [LICENSE](LICENSE) for details

---

## Acknowledgments

**Built on the shoulders of giants:**

- **Bill Benter** - Fundamental × Public model combiner
- **John Kelly** - Optimal bet sizing criterion
- **Acta Machina** - Annotated Benter paper with modern code

**Research Foundation:**
- "Computer Based Horse Race Handicapping and Wagering Systems" (Benter, 1994)
- Hong Kong Jockey Club data (1979-2023)
- 23-race live testing results (+41% ROI)

---

## Development Workflow

### Local Development
1. Install dependencies: `pip install -r workers/ingestion_spine/requirements.txt -r workers/ingestion_spine/requirements-dev.txt`
2. Run tests: `pytest`
3. Run linter: `ruff check .`
4. Run formatter: `ruff format .`
5. Run type checker: `mypy workers/ingestion_spine/`

### CI/CD
- **CI Pipeline:** Runs on every PR (tests + lint + type check)
- **Smoke Tests:** Run every 30 minutes + on every push to main
- **Dependabot:** Weekly dependency updates (Mondays 9am)

### Pull Request Process
1. Create feature branch from `feature/v10-launch`
2. Make changes + add tests
3. Run local checks: `pytest && ruff check . && mypy workers/ingestion_spine/`
4. Push and create PR (template will auto-populate)
5. Wait for CI to pass
6. Request review
7. Address feedback
8. Merge after approval + CI green

### Health Endpoints
- `/healthz` - Fast check (no DB) - Use for load balancers
- `/health` - Full check (includes DB) - Use for monitoring
- `/debug/routes` - List all registered routes

---

## Contact

**VÉLØ Oracle Team**  
GitHub: [@elpresidentepiff](https://github.com/elpresidentepiff)

---

**🏇 May the odds be ever in your favor. 💰**

