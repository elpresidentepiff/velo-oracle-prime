#!/usr/bin/env python3
"""
Deploy VÉLØ Oracle database schema to Supabase
"""
import psycopg2
import sys

# Supabase connection details
DB_CONFIG = {
    'host': 'db.ltbsxbvfsxtnharjvqcm.supabase.co',
    'port': 5432,
    'database': 'postgres',
    'user': 'postgres',
    'password': ''  # Will be provided via command line
}

def deploy_schema(password, schema_file='database/schema_v2.sql'):
    """Deploy the database schema"""
    DB_CONFIG['password'] = password
    
    print(f"🔗 Connecting to Supabase database...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.autocommit = True
        cursor = conn.cursor()
        print("✅ Connected successfully!")
        
        # Read schema file
        print(f"📖 Reading schema from {schema_file}...")
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        # Execute schema
        print("🚀 Deploying schema...")
        cursor.execute(schema_sql)
        print("✅ Schema deployed successfully!")
        
        # Verify tables
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name;
        """)
        tables = cursor.fetchall()
        
        print(f"\n📊 Created {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        cursor.close()
        conn.close()
        print("\n🎯 Deployment complete!")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 deploy_schema.py <database_password>")
        sys.exit(1)
    
    password = sys.argv[1]
    success = deploy_schema(password)
    sys.exit(0 if success else 1)
