# VÉLØ Oracle Prime: Phase 1 Changelog

**Date:** 2026-02-16
**Version:** 1.0.0

This document details the components built and changes implemented during Phase 1 of the VÉLØ Oracle Prime system upgrade. This phase was an immediate response to the Day 001 failure modes identified in the SIGMA-02 debrief at Wolverhampton.

The primary objective of Phase 1 was to introduce a series of evidence-based "hard gates" and analytical layers to prevent narrative-driven errors and enforce data-driven discipline in the selection process.

---

## 1. Core Modules Developed

Four new production-ready Python modules were created and deployed to `/src`.

### 1.1. Module 1: Market Constraint Engine

-   **File:** `src/constraints/market_engine.py`
-   **Purpose:** Provides BSP (Betfair Starting Price) drift analysis as a hard gate on selection decisions. Directly addresses the Wolverhampton failure where shortening favourites were dismissed without evidence.
-   **Key Features:**
    -   `MarketConstraintEngine` class to encapsulate all market analysis logic.
    -   `analyse_drift()`: Classifies price movement into `STEAMER`, `DRIFTER`, `STABLE`, or `VOLATILE` based on configurable percentage thresholds.
    -   `apply_constraint()`: Issues a `BLOCKED` verdict when a shortening favourite is being dismissed without at least three independent counter-signals, preventing a key Day 1 failure mode.
    -   `bsp_isp_divergence()`: Flags significant divergence between industry SP and Betfair SP, as seen with *Faster Bee* at Wolverhampton.
    -   `favourite_override_check()`: A specific hard gate to prevent assigning the `E` (Exhausted) tag to a shortening favourite, as seen with *Alondra*.
    -   All decisions and market data are persisted to a new `market_behaviour` table for post-race audit.

### 1.2. Module 2: RPD-C v2 Calibration Engine

-   **File:** `src/rpd/rpd_v2.py`
-   **Purpose:** Overhauls the Runner Profile Designation (Chaos) system to require mandatory evidence for all tag assignments. Addresses the narrative-driven, inaccurate tagging at Wolverhampton.
-   **Key Features:**
    -   `RPDv2Engine` class manages tag validation, suggestion, and auditing.
    -   **Evidence-Based Tagging:** Each RPD-C tag (`P`, `T`, `E`, `H`, `S`) now has a strict definition with a minimum number of required evidence points (e.g., `long_campaign`, `peak_fitness`).
    -   **Blocker Conditions:** Certain tags are automatically blocked under specific conditions (e.g., an `E` tag is blocked if the horse won its last race or is shortening in the market).
    -   `validate_tag()`: Checks a proposed tag against the evidence checklist and blockers.
    -   `suggest_tag()`: Recommends the most appropriate tag based on the available evidence, defaulting to `H` (Honest) if no other tag meets the criteria.
    -   `tag_audit()`: A post-race function to assess the accuracy of predicted tags against actual outcomes, generating lessons for continuous improvement.
    -   All validations are persisted to a new `rpd_validation` table.

### 1.3. Module 3: Scenario Evidence Gate

-   **File:** `src/scenarios/evidence_gate.py`
-   **Purpose:** Prevents the overuse of high-impact scenario codes (especially S6 "Hidden Intent") by requiring a minimum number of independent signals.
-   **Key Features:**
    -   `ScenarioEvidenceGate` class manages scenario validation and suggestion.
    -   **Signal-Based Scenarios:** Each scenario (S1-S8) requires a minimum count of predefined signals (e.g., `pace_shape`, `trainer_pattern`).
    -   **S6 Hard Gate:** The S6 scenario now has a **hard requirement** for the `market_shortening` signal. It cannot be assigned without market confirmation, directly addressing the repeated S6 failures at Wolverhampton.
    -   `validate_scenario()`: Approves or rejects a scenario assignment based on the evidence provided.
    -   `suggest_scenario()`: Recommends the most likely scenario, defaulting to S8 (Chaos) if evidence is insufficient for any other code.
    -   `scenario_audit()`: Assesses the accuracy of scenario predictions post-race.
    -   Results are persisted to the `sigma_evaluations` table.

### 1.4. Module 4: Track Profile Database

-   **File:** `src/tracks/track_profiles.py`
-   **Purpose:** Establishes a foundational database of UK racecourse characteristics to provide essential context for all analytical modules. Addresses the complete lack of track intelligence at Wolverhampton.
-   **Key Features:**
    -   `TrackProfileDB` class provides an interface to a comprehensive SQLite database of track data.
    -   **40+ UK Tracks:** The database is pre-loaded with detailed profiles for over 40 UK racecourses, including all All-Weather (AW) and major turf tracks.
    -   **Chaos Rating:** Each track is assigned a Chaos Rating (1-5) to quantify its predictability. Wolverhampton is rated 4/5 (High Chaos).
    -   **Detailed Profiles:** Includes surface type, direction, draw bias, pace bias, and qualitative notes.
    -   `pre_race_context()`: Generates a detailed intelligence brief for a given track, including an explicit warning for high-chaos venues.
    -   `compare_tracks()`: Provides a similarity analysis between two tracks.

---

## 2. Integration & Testing

### 2.1. Phase 1 Integration Module

-   **File:** `src/phase1_integration.py`
-   **Purpose:** Wires all four modules together into a unified, cohesive system.
-   **Key Features:**
    -   `Phase1Integration` class that initializes and provides access to all engines.
    -   `pre_race_check()`: A master function that runs a given race through all four modules, producing a consolidated intelligence brief. It checks track context, analyzes market movements, validates RPD tags, and verifies the race scenario, generating a list of critical alerts.
    -   `post_race_audit()`: A master function that runs a post-race audit across both the RPD and Scenario engines, providing a holistic view of system performance and generating actionable lessons.

### 2.2. Comprehensive Unit Tests

-   **File:** `tests/test_phase1.py`
-   **Purpose:** Ensures the reliability, correctness, and robustness of all new modules and their integration.
-   **Key Features:**
    -   **100+ Test Cases:** A comprehensive suite of unit tests covering all classes and methods.
    -   **Wolverhampton Day 1 Replay:** A dedicated test class, `TestWolverhamptonDay1Replay`, that simulates the specific failure modes from the SIGMA-02 debrief. These tests verify that the new hard gates and analytical layers successfully prevent the same errors from recurring:
        -   `test_alondra_e_tag_blocked`: Confirms the system blocks tagging a shortening favourite as 'Exhausted'.
        -   `test_cressida_wildes_steamer_detection`: Confirms the system correctly identifies a significant market steamer.
        -   `test_faster_bee_divergence_flagged`: Confirms the system flags major divergence between ISP and BSP.
        -   `test_s6_without_market_rejected`: Confirms the S6 'Hidden Intent' scenario is rejected without market confirmation.
        -   `test_wolverhampton_chaos_rating`: Confirms Wolverhampton is correctly assigned a high chaos rating.

---

## 3. Directory Structure

The project has been organized into the following structure:

```
phase1/
├── src/
│   ├── constraints/
│   │   ├── __init__.py
│   │   └── market_engine.py
│   ├── rpd/
│   │   ├── __init__.py
│   │   └── rpd_v2.py
│   ├── scenarios/
│   │   ├── __init__.py
│   │   └── evidence_gate.py
│   ├── tracks/
│   │   ├── __init__.py
│   │   └── track_profiles.py
│   └── phase1_integration.py
├── tests/
│   └── test_phase1.py
└── PHASE1_CHANGELOG.md
```
