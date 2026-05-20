"""add hfs block001 doctrine columns

Revision ID: a1b2c3d4e5f6
Revises: 
Create Date: 2026-05-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # --- 1. Signal Columns (Specialist models) ---
    op.add_column('historical_feature_store', sa.Column('market_deception_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('improvement_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('trainer_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('jockey_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('course_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('distance_score', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('pace_profile', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('field_strength', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('market_pressure', sa.Float(), nullable=True))

    # --- 2. Temporal/Leakage Safety Columns ---
    op.add_column('historical_feature_store', sa.Column('pre_race_odds_dec', sa.Float(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('odds_timestamp', sa.DateTime(timezone=True), nullable=True))
    op.add_column('historical_feature_store', sa.Column('odds_source', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('prediction_timestamp', sa.DateTime(timezone=True), nullable=True))
    op.add_column('historical_feature_store', sa.Column('leakage_status', sa.Text(), nullable=True))

    # --- 3. Provenance & Quality Columns ---
    op.add_column('historical_feature_store', sa.Column('feature_status', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('feature_quality', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('feature_provenance', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('training_safe', sa.Boolean(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('batch_id', sa.Text(), nullable=True))
    op.add_column('historical_feature_store', sa.Column('audit_id', sa.Text(), nullable=True))

    # --- 4. Indexes for Reconstruction & Audit ---
    op.create_index('ix_hfs_batch_id', 'historical_feature_store', ['batch_id'])
    op.create_index('ix_hfs_audit_id', 'historical_feature_store', ['audit_id'])
    op.create_index('ix_hfs_reconstruction_version', 'historical_feature_store', ['reconstruction_version'])
    op.create_index('ix_hfs_training_safe', 'historical_feature_store', ['training_safe'])
    op.create_index('ix_hfs_leakage_status', 'historical_feature_store', ['leakage_status'])


def downgrade():
    # --- Remove Indexes ---
    op.drop_index('ix_hfs_leakage_status', table_name='historical_feature_store')
    op.drop_index('ix_hfs_training_safe', table_name='historical_feature_store')
    op.drop_index('ix_hfs_reconstruction_version', table_name='historical_feature_store')
    op.drop_index('ix_hfs_audit_id', table_name='historical_feature_store')
    op.drop_index('ix_hfs_batch_id', table_name='historical_feature_store')

    # --- Remove Columns ---
    op.drop_column('historical_feature_store', 'audit_id')
    op.drop_column('historical_feature_store', 'batch_id')
    op.drop_column('historical_feature_store', 'training_safe')
    op.drop_column('historical_feature_store', 'feature_provenance')
    op.drop_column('historical_feature_store', 'feature_quality')
    op.drop_column('historical_feature_store', 'feature_status')
    op.drop_column('historical_feature_store', 'leakage_status')
    op.drop_column('historical_feature_store', 'prediction_timestamp')
    op.drop_column('historical_feature_store', 'odds_source')
    op.drop_column('historical_feature_store', 'odds_timestamp')
    op.drop_column('historical_feature_store', 'pre_race_odds_dec')
    op.drop_column('historical_feature_store', 'market_pressure')
    op.drop_column('historical_feature_store', 'field_strength')
    op.drop_column('historical_feature_store', 'pace_profile')
    op.drop_column('historical_feature_store', 'distance_score')
    op.drop_column('historical_feature_store', 'course_score')
    op.drop_column('historical_feature_store', 'jockey_score')
    op.drop_column('historical_feature_store', 'trainer_score')
    op.drop_column('historical_feature_store', 'improvement_score')
    op.drop_column('historical_feature_store', 'market_deception_score')
