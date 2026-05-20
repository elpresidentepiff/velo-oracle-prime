"""hfs block001 schema drift reconciliation

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-05 15:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6g7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None

def _get_column_type(table_name, column_name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    columns = insp.get_columns(table_name)
    for c in columns:
        if c['name'] == column_name:
            return str(c['type']).lower()
    return None

def _column_exists(table_name, column_name):
    return _get_column_type(table_name, column_name) is not None

def _index_exists(table_name, index_name):
    bind = op.get_bind()
    insp = sa.inspect(bind)
    indexes = insp.get_indexes(table_name)
    return any(idx['name'] == index_name for idx in indexes)

def upgrade():
    # --- 1. Signal Columns (Specialist models) ---
    for col in ['market_deception_score', 'improvement_score', 'trainer_score', 
                'jockey_score', 'course_score', 'distance_score', 'field_strength', 'market_pressure']:
        if not _column_exists('historical_feature_store', col):
            op.add_column('historical_feature_store', sa.Column(col, sa.Float(), nullable=True))
    
    # pace_profile type-aware reconciliation
    col_type = _get_column_type('historical_feature_store', 'pace_profile')
    if col_type is None:
        op.add_column('historical_feature_store', sa.Column('pace_profile', postgresql.JSONB(), nullable=True))
    elif 'json' not in col_type:
        # Convert TEXT to JSONB safely
        op.execute("""
            ALTER TABLE historical_feature_store 
            ALTER COLUMN pace_profile TYPE JSONB 
            USING CASE 
                WHEN pace_profile IS NULL OR btrim(pace_profile::text) = '' THEN NULL 
                ELSE pace_profile::jsonb 
            END;
        """)

    # --- 2. Temporal/Leakage Safety Columns ---
    if not _column_exists('historical_feature_store', 'pre_race_odds_dec'):
        op.add_column('historical_feature_store', sa.Column('pre_race_odds_dec', sa.Float(), nullable=True))
    if not _column_exists('historical_feature_store', 'odds_timestamp'):
        op.add_column('historical_feature_store', sa.Column('odds_timestamp', sa.DateTime(timezone=True), nullable=True))
    if not _column_exists('historical_feature_store', 'odds_source'):
        op.add_column('historical_feature_store', sa.Column('odds_source', sa.Text(), nullable=True))
    if not _column_exists('historical_feature_store', 'prediction_timestamp'):
        op.add_column('historical_feature_store', sa.Column('prediction_timestamp', sa.DateTime(timezone=True), nullable=True))
    if not _column_exists('historical_feature_store', 'leakage_status'):
        op.add_column('historical_feature_store', sa.Column('leakage_status', sa.Text(), nullable=True))

    # --- 3. Provenance & Quality Columns ---
    if not _column_exists('historical_feature_store', 'feature_status'):
        op.add_column('historical_feature_store', sa.Column('feature_status', sa.Text(), nullable=True))
    if not _column_exists('historical_feature_store', 'feature_quality'):
        op.add_column('historical_feature_store', sa.Column('feature_quality', sa.Text(), nullable=True))
    
    # feature_provenance type-aware reconciliation
    col_type = _get_column_type('historical_feature_store', 'feature_provenance')
    if col_type is None:
        op.add_column('historical_feature_store', sa.Column('feature_provenance', postgresql.JSONB(), nullable=True))
    elif 'json' not in col_type:
        # Convert TEXT to JSONB safely
        op.execute("""
            ALTER TABLE historical_feature_store 
            ALTER COLUMN feature_provenance TYPE JSONB 
            USING CASE 
                WHEN feature_provenance IS NULL OR btrim(feature_provenance::text) = '' THEN NULL 
                ELSE feature_provenance::jsonb 
            END;
        """)

    if not _column_exists('historical_feature_store', 'training_safe'):
        op.add_column('historical_feature_store', sa.Column('training_safe', sa.Boolean(), server_default=sa.text('false'), nullable=True))
    if not _column_exists('historical_feature_store', 'batch_id'):
        op.add_column('historical_feature_store', sa.Column('batch_id', sa.Text(), nullable=True))
    if not _column_exists('historical_feature_store', 'audit_id'):
        op.add_column('historical_feature_store', sa.Column('audit_id', sa.Text(), nullable=True))
    if not _column_exists('historical_feature_store', 'reconstruction_version'):
        op.add_column('historical_feature_store', sa.Column('reconstruction_version', sa.Text(), nullable=True))

    # --- 4. Indexes for Reconstruction & Audit ---
    idx_map = {
        'ix_hfs_batch_id': ['batch_id'],
        'ix_hfs_audit_id': ['audit_id'],
        'ix_hfs_reconstruction_version': ['reconstruction_version'],
        'ix_hfs_training_safe': ['training_safe'],
        'ix_hfs_leakage_status': ['leakage_status']
    }
    for idx_name, cols in idx_map.items():
        if not _index_exists('historical_feature_store', idx_name):
            op.create_index(idx_name, 'historical_feature_store', cols)


def downgrade():
    """
    WARNING: DESTRUCTIVE DOWNGRADE BLOCKED BY DEFAULT.
    This is a reconciliation migration intended to align repo with live DB truth.
    Dropping these columns in production may remove data manually inserted or
    reconciled. Manual approval required for destructive rollback.
    """
    # To enable downgrade, comment out the return line below.
    return 

    # --- Remove Indexes ---
    op.drop_index('ix_hfs_leakage_status', table_name='historical_feature_store')
    op.drop_index('ix_hfs_training_safe', table_name='historical_feature_store')
    op.drop_index('ix_hfs_reconstruction_version', table_name='historical_feature_store')
    op.drop_index('ix_hfs_audit_id', table_name='historical_feature_store')
    op.drop_index('ix_hfs_batch_id', table_name='historical_feature_store')

    # --- Remove Columns ---
    op.drop_column('historical_feature_store', 'reconstruction_version')
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
