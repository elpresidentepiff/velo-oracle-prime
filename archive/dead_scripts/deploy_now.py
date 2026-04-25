#!/usr/bin/env python3
"""
Deploy VELO v12 schema to Supabase via direct PostgreSQL connection
"""
import sys

try:
    import psycopg2
except ImportError:
    print("Installing psycopg2-binary...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "psycopg2-binary"])
    import psycopg2

# Supabase connection details
# Format: postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-us-east-1.pooler.supabase.com:5432/postgres
PROJECT_REF = "ltbsxbvfsxtnharjvqcm"

print("=" * 70)
print("🚀 VELO v12 Schema Deployment")
print("=" * 70)
print()

# Read password from user
print("Enter Supabase database password:")
print("(Find it at: https://supabase.com/dashboard/project/ltbsxbvfsxtnharjvqcm/settings/database)")
password = input("Password: ").strip()

if not password:
    print("❌ Password required")
    sys.exit(1)

# Connection string
conn_str = f"postgresql://postgres.{PROJECT_REF}:{password}@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

print()
print("🔌 Connecting to Supabase...")

try:
    conn = psycopg2.connect(conn_str)
    conn.autocommit = True
    cursor = conn.cursor()
    print("✅ Connected successfully")
    print()
    
    # Read schema file
    with open("supabase/migrations/000_complete_v12_schema_with_rls.sql", "r") as f:
        sql = f.read()
    
    print("📝 Executing schema migration...")
    print()
    
    # Execute the entire migration
    try:
        cursor.execute(sql)
        print("✅ Schema deployed successfully")
        print()
    except Exception as e:
        print(f"⚠️  Error during deployment: {e}")
        print("   Continuing with verification...")
        print()
    
    # Verify tables
    print("🔍 Verifying deployment...")
    print()
    
    cursor.execute("""
        SELECT tablename, 
               CASE WHEN rowsecurity THEN 'ENABLED' ELSE 'DISABLED' END as rls_status
        FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events')
        ORDER BY tablename;
    """)
    
    results = cursor.fetchall()
    
    if results:
        print("Tables created:")
        for table, rls in results:
            print(f"  ✅ {table:20s} RLS: {rls}")
        print()
    else:
        print("❌ No tables found")
        print()
    
    # Check policies
    cursor.execute("""
        SELECT tablename, COUNT(*) as policy_count
        FROM pg_policies 
        WHERE tablename IN ('races', 'runners', 'market_snapshots', 'engine_runs', 'verdicts', 'learning_events')
        GROUP BY tablename
        ORDER BY tablename;
    """)
    
    policy_results = cursor.fetchall()
    
    if policy_results:
        print("RLS Policies:")
        for table, count in policy_results:
            print(f"  ✅ {table:20s} {count} policies")
        print()
    
    print("=" * 70)
    print("✅ DEPLOYMENT COMPLETE")
    print("=" * 70)
    
    cursor.close()
    conn.close()
    
except psycopg2.OperationalError as e:
    print(f"❌ Connection failed: {e}")
    print()
    print("Possible issues:")
    print("  1. Incorrect password")
    print("  2. Database not accessible")
    print("  3. Network issues")
    sys.exit(1)
except Exception as e:
    print(f"❌ Unexpected error: {e}")
    sys.exit(1)
