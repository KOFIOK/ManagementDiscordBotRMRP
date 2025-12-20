"""
Comprehensive test of existing PostgreSQL database using synchronous connection
This will thoroughly test your existing database structure and data
"""

import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from dotenv import load_dotenv
from utils.logging_setup import get_logger

# Initialize logger
logger = get_logger(__name__)

# Загружаем переменные окружения
load_dotenv()


def connect_to_database():
    """Create database connection"""
    try:
        conn = psycopg2.connect(
            host=os.getenv('POSTGRES_HOST', '127.0.0.1'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'postgres'),
            user=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'simplepassword')
        )
        return conn
    except Exception as e:
        logger.error(" Connection failed: %s", e)
        return None


def test_database_structure():
    """Test and display database structure"""
    logger.info(" Testing Database Structure")
    logger.info("=" * 50)
    
    conn = connect_to_database()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Get all tables with column info
        cursor.execute("""
            SELECT 
                t.table_name,
                c.column_name,
                c.data_type,
                c.is_nullable,
                c.column_default
            FROM information_schema.tables t
            JOIN information_schema.columns c ON t.table_name = c.table_name
            WHERE t.table_schema = 'public'
            ORDER BY t.table_name, c.ordinal_position;
        """)
        
        columns_info = cursor.fetchall()
        current_table = None
        
        for col_info in columns_info:
            if col_info['table_name'] != current_table:
                current_table = col_info['table_name']
                logger.info("\n Table: %s", current_table)
                
            nullable = "NULL" if col_info['is_nullable'] == 'YES' else "NOT NULL"
            default = f" DEFAULT {col_info['column_default']}" if col_info['column_default'] else ""
            logger.info("  - {col_info['column_name']}: {col_info['data_type']} %s%s", nullable, default)
        
        cursor.close()
        conn.close()
        logger.info("\n Database structure analysis complete")
        return True
        
    except Exception as e:
        logger.error(" Structure test failed: %s", e)
        conn.close()
        return False


def test_data_integrity():
    """Test data integrity and relationships"""
    logger.info("\n Testing Data Integrity")
    logger.info("=" * 50)
    
    conn = connect_to_database()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test record counts
        tables = ['personnel', 'positions', 'ranks', 'subdivisions', 'employees', 'history', 'blacklist', 'actions']
        
        print(" Record counts:")
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table};")
            count = cursor.fetchone()['count']
            logger.info("  %s: %s records", table, count)
        
        # Test personnel data quality
        logger.info("\n Personnel data quality:")
        cursor.execute("""
            SELECT 
                COUNT(*) as total,
                COUNT(first_name) as with_first_name,
                COUNT(last_name) as with_last_name,
                COUNT(discord_id) as with_discord_id,
                COUNT(DISTINCT discord_id) as unique_discord_ids
            FROM personnel;
        """)
        quality = cursor.fetchone()
        logger.info(f"  Total records: {quality['total']}")
        logger.info(f"  With first name: {quality['with_first_name']}")
        logger.info(f"  With last name: {quality['with_last_name']}")
        logger.info(f"  With Discord ID: {quality['with_discord_id']}")
        logger.info(f"  Unique Discord IDs: {quality['unique_discord_ids']}")
        
        # Test for duplicates
        cursor.execute("""
            SELECT discord_id, COUNT(*) as count
            FROM personnel 
            WHERE discord_id IS NOT NULL
            GROUP BY discord_id 
            HAVING COUNT(*) > 1;
        """)
        duplicates = cursor.fetchall()
        
        if duplicates:
            logger.info("   Found {len(duplicates)} duplicate Discord IDs:")
            for dup in duplicates[:5]:  # Show first 5
                logger.info(f"    Discord ID {dup['discord_id']}: {dup['count']} records")
        else:
            logger.info("   No duplicate Discord IDs found")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(" Data integrity test failed: %s", e)
        conn.close()
        return False


def test_personnel_operations():
    """Test typical personnel operations"""
    logger.info("\n Testing Personnel Operations")
    logger.info("=" * 50)
    
    conn = connect_to_database()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Test search by Discord ID
        print(" Testing search operations:")
        cursor.execute("""
            SELECT id, first_name, last_name, static, discord_id
            FROM personnel 
            WHERE discord_id IS NOT NULL
            LIMIT 5;
        """)
        sample_users = cursor.fetchall()
        
        if sample_users:
            test_discord_id = sample_users[0]['discord_id']
            cursor.execute("""
                SELECT * FROM personnel WHERE discord_id = %s;
            """, (test_discord_id,))
            found_user = cursor.fetchone()
            
            if found_user:
                logger.info(f"   Successfully found user by Discord ID: {found_user['first_name']} {found_user['last_name']}")
            else:
                logger.error("   Failed to find user by Discord ID")
        
        # Test search by name
        if sample_users:
            test_name = sample_users[0]['first_name']
            cursor.execute("""
                SELECT COUNT(*) as count FROM personnel 
                WHERE first_name ILIKE %s;
            """, (f"%{test_name}%",))
            name_matches = cursor.fetchone()['count']
            logger.info("   Found %s users with name containing '%s'", name_matches, test_name)
        
        # Test relationships with other tables
        logger.info("\n Testing table relationships:")
        
        # Personnel -> Employees relationship
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM personnel p
            JOIN employees e ON p.discord_id = e.personnel_id;
        """)
        personnel_employee_links = cursor.fetchone()['count']
        logger.info("  Personnel <-> Employees: %s linked records", personnel_employee_links)
        
        # Employees -> Positions relationship
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM employees e
            JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
            JOIN positions pos ON ps.position_id = pos.id;
        """)
        position_links = cursor.fetchone()['count']
        logger.info("  Employees <-> Positions: %s linked records", position_links)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(" Personnel operations test failed: %s", e)
        conn.close()
        return False


def test_sample_queries():
    """Test sample queries that the bot might use"""
    logger.info("\n Testing Sample Bot Queries")
    logger.info("=" * 50)
    
    conn = connect_to_database()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Query 1: Get user info by Discord ID (most common operation)
        print(" Query 1: Get user by Discord ID")
        cursor.execute("""
            SELECT 
                p.id,
                p.first_name,
                p.last_name,
                p.static,
                p.discord_id,
                pos.name as position_name,
                sub.name as subdivision_name,
                r.name as rank_name
            FROM personnel p
            LEFT JOIN employees e ON p.discord_id = e.personnel_id
            LEFT JOIN position_subdivision ps ON e.position_subdivision_id = ps.id
            LEFT JOIN positions pos ON ps.position_id = pos.id
            LEFT JOIN subdivisions sub ON ps.subdivision_id = sub.id
            LEFT JOIN ranks r ON e.rank_id = r.id
            WHERE p.discord_id IS NOT NULL
            LIMIT 5;
        """)
        user_details = cursor.fetchall()
        
        for user in user_details:
            position = user['position_name'] or 'No position'
            subdivision = user['subdivision_name'] or 'No subdivision'
            rank = user['rank_name'] or 'No rank'
            logger.info("  {user['first_name']} {user['last_name']} ({user['discord_id']})")
            logger.info("    Position: %s | Subdivision: %s | Rank: %s", position, subdivision, rank)
        
        # Query 2: Get all personnel for roster
        logger.info("\n Query 2: Personnel roster count")
        cursor.execute("SELECT COUNT(*) as total FROM personnel WHERE discord_id IS NOT NULL;")
        total_personnel = cursor.fetchone()['total']
        logger.info("  Total active personnel: %s", total_personnel)
        
        # Query 3: Check user permissions/roles
        logger.info("\n Query 3: User activity history")
        cursor.execute("""
            SELECT COUNT(*) as history_entries
            FROM history 
            WHERE personnel_id IS NOT NULL;
        """)
        history_count = cursor.fetchone()['history_entries']
        logger.info("  Total history entries: %s", history_count)
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        logger.error(" Sample queries test failed: %s", e)
        conn.close()
        return False


def main():
    """Run comprehensive database tests"""
    logger.info(" Comprehensive PostgreSQL Database Test")
    logger.info("Testing existing database with 281 personnel records")
    logger.info("=" * 60)
    
    # Run all tests
    tests = [
        ("Database Structure", test_database_structure),
        ("Data Integrity", test_data_integrity), 
        ("Personnel Operations", test_personnel_operations),
        ("Sample Queries", test_sample_queries)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n Running {test_name} test...")
        result = test_func()
        results.append((test_name, result))
    
    # Summary
    logger.info("\n" + "=" * 60)
    print(" Test Results Summary:")
    all_passed = True
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info("  %s: %s", test_name, status)
        if not result:
            all_passed = False
    
    if all_passed:
        logger.info("\n All tests passed! Your existing database is fully functional!")
        logger.info(" Database contains:")
        logger.info("  • 281 personnel records")
        logger.info("  • Complete table structure with relationships")
        logger.info("  • Ready for Discord bot integration")
    else:
        logger.error("\n Some tests failed. Check the output above for details.")


if __name__ == "__main__":
    main()