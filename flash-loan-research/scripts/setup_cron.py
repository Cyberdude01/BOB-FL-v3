#!/usr/bin/env python3
"""
Cron Job Setup for Flash Loan Research System
Sets up automated monitoring and reporting schedules
"""

import os
import subprocess
import logging
from datetime import datetime

class CronJobManager:
    """Manages cron jobs for flash loan monitoring"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.logger = logging.getLogger(__name__)
        
        # Define cron jobs
        self.cron_jobs = {
            "monitor": {
                "schedule": "*/30 * * * *",  # Every 30 minutes
                "command": f"cd {project_root} && python scripts/monitor.py --single-run >> logs/cron.log 2>&1",
                "description": "Flash loan opportunity monitoring every 30 minutes"
            },
            "daily_report": {
                "schedule": "0 9 * * *",  # Daily at 9:00 UTC
                "command": f"cd {project_root} && python scripts/report_generator.py >> logs/cron.log 2>&1",
                "description": "Generate daily flash loan research report"
            },
            "data_cleanup": {
                "schedule": "0 2 * * *",  # Daily at 2:00 UTC
                "command": f"cd {project_root} && find data/raw -name '*.json' -mtime +7 -delete >> logs/cron.log 2>&1",
                "description": "Clean up old raw data files (older than 7 days)"
            },
            "weekly_summary": {
                "schedule": "0 10 * * 1",  # Every Monday at 10:00 UTC
                "command": f"cd {project_root} && python scripts/weekly_summary.py >> logs/cron.log 2>&1",
                "description": "Generate weekly opportunity summary"
            }
        }
    
    def setup_cron_jobs(self):
        """Set up all cron jobs"""
        self.logger.info("Setting up cron jobs for flash loan research")
        
        # Create backup of existing crontab
        try:
            subprocess.run("crontab -l > /tmp/crontab_backup", shell=True, check=True)
            self.logger.info("Existing crontab backed up to /tmp/crontab_backup")
        except subprocess.CalledProcessError:
            self.logger.info("No existing crontab found")
        
        # Generate new crontab content
        crontab_content = "# Flash Loan Research System - Auto-generated\n"
        crontab_content += "# Created: " + datetime.now().isoformat() + "\n\n"
        
        for job_name, job_config in self.cron_jobs.items():
            crontab_content += f"# {job_config['description']}\n"
            crontab_content += f"{job_config['schedule']} {job_config['command']}\n\n"
        
        # Add environment variables
        crontab_content += "# Environment variables\n"
        crontab_content += "PATH=/usr/bin:/bin\n"
        crontab_content += f"PROJECT_ROOT={self.project_root}\n\n"
        
        # Write to temporary file
        with open("/tmp/new_crontab", "w") as f:
            f.write(crontab_content)
        
        # Install new crontab
        try:
            subprocess.run("crontab /tmp/new_crontab", shell=True, check=True)
            self.logger.info("Cron jobs installed successfully")
            
            # Show current cron jobs
            result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
            print("Current cron jobs:")
            print(result.stdout)
            
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error installing cron jobs: {e}")
            raise
    
    def remove_cron_jobs(self):
        """Remove flash loan research cron jobs"""
        self.logger.info("Removing flash loan research cron jobs")
        
        # Get current crontab
        try:
            result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
            current_crontab = result.stdout
            
            # Remove flash loan related lines
            lines = current_crontab.split('\n')
            filtered_lines = []
            
            for line in lines:
                if 'flash-loan-research' in line or 'monitor.py' in line or 'report_generator.py' in line:
                    continue
                # Skip empty lines that are part of our job blocks
                if line.strip() and not line.startswith('#') and len(filtered_lines) > 0 and filtered_lines[-1].startswith('# Flash Loan'):
                    continue
                filtered_lines.append(line)
            
            # Write filtered crontab
            filtered_crontab = '\n'.join(filtered_lines)
            with open("/tmp/filtered_crontab", "w") as f:
                f.write(filtered_crontab)
            
            # Install filtered crontab
            subprocess.run("crontab /tmp/filtered_crontab", shell=True, check=True)
            self.logger.info("Flash loan cron jobs removed successfully")
            
        except subprocess.CalledProcessError:
            self.logger.info("No crontab found or error removing jobs")
    
    def list_cron_jobs(self):
        """List current cron jobs"""
        try:
            result = subprocess.run("crontab -l", shell=True, capture_output=True, text=True)
            print("Current cron jobs:")
            print(result.stdout)
        except subprocess.CalledProcessError:
            print("No crontab found")

def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Setup cron jobs for flash loan research")
    parser.add_argument("--setup", action="store_true", help="Setup cron jobs")
    parser.add_argument("--remove", action="store_true", help="Remove cron jobs")
    parser.add_argument("--list", action="store_true", help="List current cron jobs")
    parser.add_argument("--project-root", help="Project root directory", 
                       default="/root/.openclaw/workspace/flash-loan-research")
    
    args = parser.parse_args()
    
    # Initialize cron manager
    cron_manager = CronJobManager(args.project_root)
    
    if args.setup:
        cron_manager.setup_cron_jobs()
    elif args.remove:
        cron_manager.remove_cron_jobs()
    elif args.list:
        cron_manager.list_cron_jobs()
    else:
        print("Please specify an action: --setup, --remove, or --list")

if __name__ == "__main__":
    main()