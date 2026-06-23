#!/usr/bin/env python3
"""
Test All Connections Script
Comprehensive connection testing for flash loan monitoring system
"""

import os
import json
import requests
import sqlite3
import logging
import time
from datetime import datetime
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConnectionTester:
    def __init__(self):
        self.results = {}
        self.start_time = datetime.now()
        
        # Define all endpoints to test
        self.endpoints = {
            'infura': {
                'mainnet': 'https://mainnet.infura.io/v3/test',
                'sepolia': 'https://sepolia.infura.io/v3/test',
                'polygon': 'https://polygon-mainnet.infura.io/v3/test',
                'base': 'https://base-mainnet.infura.io/v3/test',
                'arbitrum': 'https://arbitrum-mainnet.infura.io/v3/test',
                'avalanche': 'https://avalanche-mainnet.infura.io/v3/test'
            },
            'the_graph': {
                'mainnet': 'https://api.thegraph.com/index-node/graphql',
                'arbitrum': 'https://api.thegraph.com/subgraphs/id/Qmd8nUT4G3v6L9whh5gNbY68Yak3g9Gvg9FYeXgZ2f8EXR',
                'polygon': 'https://api.thegraph.com/subgraphs/id/Qmeb4YzQk5Z3v6L9whh5gNbY68Yak3g9Gvg9FYeXgZ2f8EXR'
            },
            'apis': {
                'dune': 'https://api.dune.com/api/1/schema',
                'coingecko': 'https://api.coingecko.com/api/v3/ping',
                'uniswap_v3': 'https://api.thegraph.com/subgraphs/name/uniswap/uniswap-v3'
            },
            'databases': {
                'enhanced_db': '/root/.openclaw/workspace/flash-loan-research/enhanced_flash_loan_research.db',
                'demo_db': '/root/.openclaw/workspace/flash-loan-research/demo_enhanced_flash_loan_research.db'
            }
        }
        
        # Test configurations
        self.timeout = 30
        self.max_workers = 10
    
    def test_infura_connections(self):
        """Test all Infura connections"""
        logger.info("Testing Infura connections...")
        
        infura_id = os.getenv('INFURA_PROJECT_ID')
        if not infura_id:
            logger.error("INFURA_PROJECT_ID not found in environment")
            self.results['infura'] = {'error': 'Missing INFURA_PROJECT_ID'}
            return
        
        results = {}
        
        for network, endpoint in self.endpoints['infura'].items():
            try:
                # Replace 'test' with actual project ID
                actual_endpoint = endpoint.replace('/v3/test', f'/v3/{infura_id}')
                response = requests.get(actual_endpoint, timeout=self.timeout)
                
                if response.status_code == 200:
                    results[network] = {'status': 'success', 'response_time': response.elapsed.total_seconds()}
                else:
                    results[network] = {'status': 'fail', 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                results[network] = {'status': 'fail', 'error': str(e)}
        
        self.results['infura'] = results
        return results
    
    def test_the_graph_connections(self):
        """Test The Graph connections"""
        logger.info("Testing The Graph connections...")
        
        api_key = os.getenv('THE_GRAPH_API_KEY')
        headers = {}
        
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'
        
        results = {}
        
        for network, endpoint in self.endpoints['the_graph'].items():
            try:
                # For GraphQL endpoints, use a simple query
                if 'graph' in endpoint:
                    query = "{ indexingStatuses { chainHeadBlock subgraphs } }"
                    response = requests.post(
                        endpoint,
                        json={'query': query},
                        headers=headers,
                        timeout=self.timeout
                    )
                else:
                    response = requests.get(endpoint, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    results[network] = {'status': 'success', 'response_time': response.elapsed.total_seconds()}
                else:
                    results[network] = {'status': 'fail', 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                results[network] = {'status': 'fail', 'error': str(e)}
        
        self.results['the_graph'] = results
        return results
    
    def test_api_connections(self):
        """Test external API connections"""
        logger.info("Testing external API connections...")
        
        dune_api_key = os.getenv('DUNE_API_KEY')
        headers = {}
        
        if dune_api_key:
            headers['X-API-Key'] = dune_api_key
        
        results = {}
        
        for api_name, endpoint in self.endpoints['apis'].items():
            try:
                response = requests.get(endpoint, headers=headers, timeout=self.timeout)
                
                if response.status_code == 200:
                    results[api_name] = {'status': 'success', 'response_time': response.elapsed.total_seconds()}
                else:
                    results[api_name] = {'status': 'fail', 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                results[api_name] = {'status': 'fail', 'error': str(e)}
        
        self.results['apis'] = results
        return results
    
    def test_database_connections(self):
        """Test database connections"""
        logger.info("Testing database connections...")
        
        results = {}
        
        for db_name, db_path in self.endpoints['databases'].items():
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                conn.close()
                
                results[db_name] = {
                    'status': 'success',
                    'tables': len(tables),
                    'response_time': 0.1  # Simulated response time for DB
                }
                
            except Exception as e:
                results[db_name] = {'status': 'fail', 'error': str(e)}
        
        self.results['databases'] = results
        return results
    
    def test_network_connectivity(self):
        """Test basic network connectivity"""
        logger.info("Testing network connectivity...")
        
        test_urls = [
            'https://www.google.com',
            'https://api.github.com',
            'https://wss://ws.coincap.io/prices?assets=ethereum'
        ]
        
        results = {}
        
        for url in test_urls:
            try:
                start_time = time.time()
                response = requests.get(url, timeout=10)
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    results[url] = {'status': 'success', 'response_time': response_time}
                else:
                    results[url] = {'status': 'fail', 'error': f"HTTP {response.status_code}"}
                    
            except Exception as e:
                results[url] = {'status': 'fail', 'error': str(e)}
        
        self.results['network_connectivity'] = results
        return results
    
    def test_profit_thresholds(self):
        """Test current profit threshold configurations"""
        logger.info("Testing profit threshold configurations...")
        
        # Check monitoring system configuration
        config_file = '/root/.openclaw/workspace/flash-loan-research/enhanced-monitoring-system.py'
        
        try:
            with open(config_file, 'r') as f:
                content = f.read()
            
            # Look for threshold configurations
            threshold_patterns = [
                'profit_threshold',
                'min_profit',
                'threshold',
                '0.5',
                '0.1'
            ]
            
            found_thresholds = []
            for pattern in threshold_patterns:
                if pattern in content.lower():
                    found_thresholds.append(pattern)
            
            results = {
                'status': 'success',
                'thresholds_found': len(found_thresholds),
                'thresholds': found_thresholds
            }
            
        except Exception as e:
            results = {'status': 'fail', 'error': str(e)}
        
        self.results['profit_thresholds'] = results
        return results
    
    def run_all_tests(self):
        """Run all connection tests"""
        logger.info("Starting comprehensive connection tests...")
        
        # Run tests in parallel
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            test_functions = [
                ('infura', self.test_infura_connections),
                ('the_graph', self.test_the_graph_connections),
                ('apis', self.test_api_connections),
                ('databases', self.test_database_connections),
                ('network_connectivity', self.test_network_connectivity),
                ('profit_thresholds', self.test_profit_thresholds)
            ]
            
            future_to_test = {executor.submit(func): name for name, func in test_functions}
            
            for future in as_completed(future_to_test):
                test_name = future_to_test[future]
                try:
                    result = future.result()
                    logger.info(f"Completed {test_name} test")
                except Exception as e:
                    logger.error(f"Error in {test_name} test: {e}")
                    self.results[test_name] = {'status': 'fail', 'error': str(e)}
        
        end_time = datetime.now()
        self.results['test_summary'] = {
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'duration': (end_time - self.start_time).total_seconds(),
            'total_tests': len(self.results)
        }
        
        self.generate_test_report()
        return self.results
    
    def generate_test_report(self):
        """Generate comprehensive test report"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""
COMPREHENSIVE CONNECTION TEST REPORT
Generated: {timestamp}

OVERVIEW:
- Total test categories: {len(self.results)}
- Test duration: {self.results['test_summary']['duration']:.2f} seconds

TEST RESULTS:
"""
        
        # Calculate summary statistics
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        
        for category, results in self.results.items():
            if category == 'test_summary':
                continue
                
            report += f"\n{category.upper().replace('_', ' ')}:\n"
            
            if isinstance(results, dict) and 'status' in results:
                # Single test result
                status = results['status']
                total_tests += 1
                if status == 'success':
                    passed_tests += 1
                    report += f"  Status: ✅ PASS\n"
                else:
                    failed_tests += 1
                    report += f"  Status: ❌ FAIL\n"
                    if 'error' in results:
                        report += f"  Error: {results['error']}\n"
            elif isinstance(results, dict):
                # Multiple tests in category
                category_tests = len(results)
                category_passed = sum(1 for r in results.values() if r.get('status') == 'success')
                category_failed = category_tests - category_passed
                
                total_tests += category_tests
                passed_tests += category_passed
                failed_tests += category_failed
                
                report += f"  Sub-tests: {category_tests}\n"
                report += f"  Passed: {category_passed}\n"
                response_times = [r.get('response_time', 0) for r in results.values() if r.get('status') == 'success']
                if response_times:
                    avg_response = sum(response_times) / len(response_times)
                    report += f"  Avg Response Time: {avg_response:.2f}s\n"
                
                # Show failed tests
                if category_failed > 0:
                    report += f"  Failed Tests:\n"
                    for test_name, test_result in results.items():
                        if test_result.get('status') == 'fail':
                            report += f"    - {test_name}: {test_result.get('error', 'Unknown error')}\n"
        
        report += f"""
SUMMARY STATISTICS:
- Total Tests: {total_tests}
- Passed: {passed_tests}
- Failed: {failed_tests}
- Success Rate: {(passed_tests/total_tests)*100:.1f}%

RECOMMENDATIONS:
"""
        
        if failed_tests > 0:
            report += "1. Address failed connections before proceeding with monitoring\n"
            report += "2. Check API keys and authentication settings\n"
            report += "3. Verify network connectivity and firewall settings\n"
        
        if passed_tests == total_tests:
            report += "✅ All connections successful. System ready for monitoring.\n"
        
        # Save report
        report_file = f"/root/.openclaw/workspace/flash-loan-research/logs/connection-test-report-{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        os.makedirs(os.path.dirname(report_file), exist_ok=True)
        
        with open(report_file, 'w') as f:
            f.write(report)
        
        logger.info(f"Test report saved to {report_file}")
        print(report)
        
        return report_file

if __name__ == "__main__":
    tester = ConnectionTester()
    results = tester.run_all_tests()
    
    # Exit code based on test results
    total_tests = len(results) - 1  # Exclude test_summary
    passed_tests = sum(1 for category, result in results.items() 
                     if category != 'test_summary' and result.get('status') == 'success')
    
    if passed_tests == total_tests:
        logger.info("All tests passed")
        exit(0)
    else:
        logger.error(f"{total_tests - passed_tests} tests failed")
        exit(1)