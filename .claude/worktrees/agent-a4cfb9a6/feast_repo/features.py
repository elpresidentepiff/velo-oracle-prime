"""
VÉLØ Oracle - Feast Feature Definitions
Production-grade feature store for racing predictions
"""
from datetime import timedelta
from feast import Entity, Feature, FeatureView, Field, FileSource
from feast.types import Float32, Int64, String


# ============================================================================
# ENTITIES
# ============================================================================

horse_entity = Entity(
    name="horse_id",
    description="Unique identifier for a horse"
)

trainer_entity = Entity(
    name="trainer_id",
    description="Unique identifier for a trainer"
)

jockey_entity = Entity(
    name="jockey_id",
    description="Unique identifier for a jockey"
)

race_entity = Entity(
    name="race_id",
    description="Unique identifier for a race"
)


# ============================================================================
# DATA SOURCES
# ============================================================================

# Trainer features source
trainer_features_source = FileSource(
    name="trainer_features_source",
    path="data/feast/trainer_features.parquet",
    timestamp_field="event_timestamp"
)

# Jockey features source
jockey_features_source = FileSource(
    name="jockey_features_source",
    path="data/feast/jockey_features.parquet",
    timestamp_field="event_timestamp"
)

# Horse features source
horse_features_source = FileSource(
    name="horse_features_source",
    path="data/feast/horse_features.parquet",
    timestamp_field="event_timestamp"
)

# Race features source
race_features_source = FileSource(
    name="race_features_source",
    path="data/feast/race_features.parquet",
    timestamp_field="event_timestamp"
)


# ============================================================================
# FEATURE VIEWS
# ============================================================================

trainer_velocity_features = FeatureView(
    name="trainer_velocity_features",
    entities=[trainer_entity],
    ttl=timedelta(days=90),
    schema=[
        Field(name="trainer_sr_14d", dtype=Float32),
        Field(name="trainer_sr_30d", dtype=Float32),
        Field(name="trainer_sr_90d", dtype=Float32),
        Field(name="trainer_roi_14d", dtype=Float32),
        Field(name="trainer_roi_30d", dtype=Float32),
        Field(name="trainer_roi_90d", dtype=Float32),
        Field(name="trainer_total_runs", dtype=Int64),
        Field(name="trainer_win_rate", dtype=Float32),
    ],
    source=trainer_features_source,
    description="Trainer velocity and performance metrics over rolling windows"
)

jockey_velocity_features = FeatureView(
    name="jockey_velocity_features",
    entities=[jockey_entity],
    ttl=timedelta(days=90),
    schema=[
        Field(name="jockey_sr_14d", dtype=Float32),
        Field(name="jockey_sr_30d", dtype=Float32),
        Field(name="jockey_sr_90d", dtype=Float32),
        Field(name="jockey_roi_14d", dtype=Float32),
        Field(name="jockey_roi_30d", dtype=Float32),
        Field(name="jockey_roi_90d", dtype=Float32),
        Field(name="jockey_total_runs", dtype=Int64),
        Field(name="jockey_win_rate", dtype=Float32),
    ],
    source=jockey_features_source,
    description="Jockey velocity and performance metrics over rolling windows"
)

horse_form_features = FeatureView(
    name="horse_form_features",
    entities=[horse_entity],
    ttl=timedelta(days=30),
    schema=[
        Field(name="form_ewma", dtype=Float32),
        Field(name="form_slope", dtype=Float32),
        Field(name="form_var", dtype=Float32),
        Field(name="layoff_days", dtype=Int64),
        Field(name="layoff_penalty", dtype=Float32),
        Field(name="freshness_flag", dtype=Int64),
        Field(name="class_drop", dtype=Int64),
        Field(name="classdrop_flag", dtype=Int64),
        Field(name="total_runs", dtype=Int64),
        Field(name="win_rate", dtype=Float32),
    ],
    source=horse_features_source,
    description="Horse form and performance metrics"
)

race_context_features = FeatureView(
    name="race_context_features",
    entities=[race_entity],
    ttl=timedelta(days=1),
    schema=[
        Field(name="course_going_iv", dtype=Float32),
        Field(name="draw_iv", dtype=Float32),
        Field(name="bias_persist_flag", dtype=Int64),
        Field(name="field_size", dtype=Int64),
        Field(name="race_class", dtype=Int64),
        Field(name="distance_furlongs", dtype=Float32),
        Field(name="going_code", dtype=Int64),
    ],
    source=race_features_source,
    description="Race context and environmental features"
)

# trainer_jockey_combo_features = FeatureView(
#     name="trainer_jockey_combo_features",
#     entities=[trainer_entity, jockey_entity],
#     ttl=timedelta(days=90),
#     schema=[
#         Field(name="tj_combo_uplift", dtype=Float32),
#         Field(name="tj_combo_runs", dtype=Int64),
#         Field(name="tj_combo_win_rate", dtype=Float32),
#     ],
#     source=trainer_features_source,  # Combined in trainer source
#     description="Trainer-Jockey combination synergy metrics"
# )


# ============================================================================
# ON-DEMAND FEATURE VIEWS (for real-time transformations)
# ============================================================================

# Note: On-demand features would be added here for real-time calculations
# Example: odds normalization, market pressure, etc.
# These are calculated at inference time from request data
