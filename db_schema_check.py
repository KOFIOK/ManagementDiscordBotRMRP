#!/usr/bin/env python3
"""
Database schema check script
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

def check_database_schema():
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
            database=os.getenv('POSTGRES_DB', 'postgres'),
            user=os.getenv('POSTGRES_USER', 'postgres'), 
            password=os.getenv('POSTGRES_PASSWORD', 'simplepassword')
        )
        
        with conn.cursor(cursor_factory=RealDictCursor) as cursor:
            # Positions table structure (reference)
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'positions' 
                ORDER BY ordinal_position
            """)
            positions_schema = cursor.fetchall()
            
            print("POSITIONS TABLE STRUCTURE (reference):")
            for col in positions_schema:
                nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                print(f"  {col['column_name']}: {col['data_type']} ({nullable})")
            
            # Ranks table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'ranks' 
                ORDER BY ordinal_position
            """)
            ranks_schema = cursor.fetchall()
            
            print("\nRANKS TABLE STRUCTURE:")
            for col in ranks_schema:
                nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                print(f"  {col['column_name']}: {col['data_type']} ({nullable})")
            
            # Subdivisions table structure
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'subdivisions' 
                ORDER BY ordinal_position
            """)
            subdivisions_schema = cursor.fetchall()
            
            print("\nSUBDIVISIONS TABLE STRUCTURE:")
            for col in subdivisions_schema:
                nullable = "NULL" if col["is_nullable"] == "YES" else "NOT NULL"
                print(f"  {col['column_name']}: {col['data_type']} ({nullable})")
            
            # Sample ranks data
            cursor.execute("SELECT * FROM ranks ORDER BY id LIMIT 5")
            ranks_data = cursor.fetchall()
            
            print("\nRANKS DATA SAMPLE:")
            for rank in ranks_data:
                role_id = rank.get('role_id', 'NULL')
                rank_level = rank.get('rank_level', 'NULL')
                print(f"  ID {rank['id']}: {rank['name']} | role_id: {role_id} | rank_level: {rank_level}")
            
            # Subdivisions data
            cursor.execute("SELECT * FROM subdivisions ORDER BY id")
            subdivisions_data = cursor.fetchall()
            
            print("\nSUBDIVISIONS DATA:")
            for subdivision in subdivisions_data:
                abbr = subdivision.get('abbreviation', 'NULL')
                print(f"  ID {subdivision['id']}: {subdivision['name']} | abbreviation: {abbr}")
        
        conn.close()
        
    except Exception as e:
        print(f"Database schema check error: {e}")

if __name__ == "__main__":
    check_database_schema()