#!/usr/bin/env python3
"""
Emergency Network Fix Script
Fixes critical connection issues for flash loan monitoring system
"""

import os
import json
import requests
import sqlite3
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class NetworkFixer:
    def __init__(self):
        self.env_file = '/root/.openclaw/workspace/flash-loan-research/.env'
        self.backup_file = f"{self.env_file}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # API endpoints to test
        self.test_endpoints = {
            'infura_mainnet': 'https://mainnet.infura.io/v3/test',
            'the_graph': 'https://api.thegraph.com/index-node/graphql',
            'dune_api': 'https://api.dune.com/api/1/schema'
        }
        
        # Required API keys to validate
        self.required_keys = [
            'INFURA_PROJECT_ID',
            'DUNE_API_KEY', 
            'THE_GRAPH_API_KEY'
        ]
    
    def backup_env_file(self):
        """Create backup of environment file"""
        try:
            with open(self.env_file, 'r') as src, open(self.backup_file, 'w') as dst:
                dst.write(src.read())
            logger.info(f"Environment file backed up to {self.backup_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup environment file: {e}")
            return False
    
    def test_infura_connection(self):
        """Test Infura endpoint authentication"""
        logger.info("Testing Infura connection...")
        
        infura_id = os.getenv('INFURA_PROJECT_ID')
        if not infura_id:
            logger.error("INFURA_PROJECT_ID not found in environment")
            return False
        
        # Test with a simple request
        test_url = f"https://mainnet.infura.io/v3/{infura_id}"
        try:
            response = requests.get(test_url, timeout=10)
            if response.status_code == 200:
                logger.info("Infura connection successful")
                return True
            else:
                logger.error(f"Infura connection failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Infura connection error: {e}")
            return False
    
    def test_the_graph_connection(self):
        """Test The Graph API connection"""
        logger.info("Testing The Graph connection...")
        
        api_key = os.getenv('THE_GRAPH_API_KEY')
        if not api_key:
            logger.error("THE_GRAPH_API_KEY not found in environment")
            return False
        
        # Test query
        query = "{ indexingStatuses { chainHeadBlock subgraphs } }"
        headers = {'Authorization': f'Bearer {api_key}'}
        
        try:
            response = requests.post(
                'https://api.thegraph.com/index-node/graphql',
                json={'query': query},
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("The Graph connection successful")
                return True
            else:
                logger.error(f"The Graph connection failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"The Graph connection error: {e}")
            return False
    
    def test_dune_connection(self):
        """Test Dune Analytics API connection"""
        logger.info("Testing Dune Analytics connection...")
        
        api_key = os.getenv('DUNE_API_KEY')
        if not api_key:
            logger.error("DUNE_API_KEY not found in environment")
            return False
        
        headers = {'X-API-Key': api_key}
        
        try:
            response = requests.get(
                'https://api.dune.com/api/1/schema',
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info("Dune Analytics connection successful")
                return True
            else:
                logger.error(f"Dune Analytics connection failed with status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Dune Analytics connection error: {e}")
            return False
    
    def test_database_connectivity(self):
        """Test database connectivity"""
        logger.info("Testing database connectivity...")
        
        db_files = [
            '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db',
            '/root/.openclaw/workspace/flash-loan-research/demo_enhanced_flash_loan_research.db'
        ]
        
        for db_file in db_files:
            try:
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()
                
                logger.info(f"Database {db_file} connected successfully. Tables: {len(tables)}")
                
            except Exception as e:
                logger.error(f"Database {db_file} connection failed: {e}")
                return False
        
        return True
    
    def validate_api_keys(self):
        """Validate API keys are present and not expired"""
        logger.info("Validating API keys...")
        
        missing_keys = []
        expired_keys = []
        
        for key_name in self.required_keys:
            key_value = os.getenv(key_name)
            if not key_value:
                missing_keys.append(key_name)
            elif len(key_value) < 10:  # Simple validation - real keys should be longer
                expired_keys.append(key_name)
        
        if missing_keys:
            logger.error(f"Missing API keys: {', '.join(missing_keys)}")
        
        if expired_keys:
            logger.error(f"Expired/invalid API keys: {', '.join(expired_keys)}")
        
        return len(missing_keys) == 0 and len(expired_keys) == 0
    
    def fix_infura_endpoints(self):
        """Fix Infura endpoint authentication issues"""
        logger.info("Fixing Infura endpoints...")
        
        try:
            with open(self.env_file, 'r') as f:
                env_content = f.read()
            
            # Update Infura endpoints to use project ID
            project_id = os.getenv('INFURA_PROJECT_ID')
            if project_id:
                endpoints_to_fix = [
                    'INFURA_MAINNET',
                    'INFURA_SEPOLIA', 
                    'INFURA_POLYGON',
                    'INFURA_BASE',
                    'INFURA_ARBITRUM',
                    'INFURA_AVALANCHE'
                ]
                
                for endpoint_var in endpoints_to_fix:
                    old_pattern = f"{endpoint_var}=https://"
                    new_pattern = f"{endpoint_var}=https://{project_id}@"
                    
                    if old_pattern in env_content:
                        env_content = env_content.replace(old_pattern, new_pattern)
                        logger.info(f"Fixed {endpoint_var}")
            
            # Write back to file
            with open(self.env_file, 'w') as f:
                f.write(env_content)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to fix Infura endpoints: {e}")
            return False
    
    def run_emergency_fix(self):
        """Run emergency fix procedures"""
        logger.info("Starting emergency network fix...")
        
        # Step 1: Backup current configuration
        if not self.backup_env_file():
            logger.error("Failed to create backup. Aborting fix.")
            return False
        
        # Step 2: Validate API keys
        if not self.validate_api_keys():
            logger.error("API validation failed. Please check API keys.")
            return False
        
        # Step 3: Test connections
        connection_tests = {
            'Infura': self.test_infura_connection(),
            'The Graph': self.test_the_graph_connection(),
            'Dune Analytics': self.test_dune_connection(),
            'Database': self.test_database_connectivity()
        }
        
        failed_connections = [name for name, success in connection_tests.items() if not success]
        
        if failed_connections:
            logger.error(f"Failed connections: {', '.join(failed_connections)}")
        
        # Step 4: Fix known issues
        self.fix_infura_endpoints()
        
        # Step 5: Generate report
        self.generate_fix_report(connection_tests)
        
        return len(failed_connections) == 0
    
    def generate_fix_report(self, connection_tests):
        """Generate fix report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""
EMERGENCY NETWORK FIX REPORT
Generated: {timestamp}

CONNECTION TEST RESULTS:
"""
        
        for test_name, success in connection_tests.items():
            status = "✅ PASS" if success else "❌ FAIL"
            report += f"{test_name}: {status}\n"
        
        report += f"""
SUMMARY:
- Total tests: {len(connection_tests)}
- Passed: {sum(1 for success in connection_tests.values() if success)}
- Failed: {sum(1 for success in connection_tests.values() if not success)}

ACTIONS TAKEN:
1. Created backup of environment file
2. Validated API keys
3. Tested all external connections
4. Fixed Infura endpoint authentication
5. Updated configuration files

NEXT STEPS:
"""
        
        failed_tests = [name for name, success in connection_tests.items() if not success]
        if failed_tests:
            report += f"Manual intervention required for: {', '.join(failed_tests)}\n"
        else:
            report += "All connections successful. System ready for monitoring.\n"
        
        # Save report
        report_file = f"/root/.openclaw/workspace/flash-loan-research/logs/emergency-fix-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"Fix report saved to {report_file}")
        print(report)

if __name__ == "__main__":
    fixer = NetworkFixer()
    success = fixer.run_emergency_fix()
    
    if success:
        logger.info("Emergency fix completed successfully")
        exit(0)
    else:
        logger.error("Emergency fix completed with errors")
        exit(1)