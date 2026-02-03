#!/usr/bin/env python3
"""
Anaconda MVP Deployment Script via Ansible

Usage:
    python3 deploy.py --hosts inventory.yml --env production --verbose
    python3 deploy.py --hosts 192.168.1.100 --user nsadmin
    python3 deploy.py --help
"""

import argparse
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List

class AnsiColors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class DeploymentConfig:
    """Deployment configuration"""
    
    def __init__(self, args):
        self.hosts = args.hosts
        self.user = args.user
        self.port = args.port
        self.env = args.env
        self.verbose = args.verbose
        self.dry_run = args.dry_run
        self.tags = args.tags
        self.skip_tags = args.skip_tags
        self.check_mode = args.check
        
        # Project paths
        self.project_root = Path(__file__).parent
        self.inventory_dir = self.project_root / "infrastructure"
        self.playbook_file = self.inventory_dir / "deploy.yml"
        
    def validate(self) -> bool:
        """Validate configuration"""
        if not self.playbook_file.exists():
            print(f"{AnsiColors.FAIL}❌ Playbook not found: {self.playbook_file}{AnsiColors.ENDC}")
            return False
        
        # Check if hosts is a file or inventory string
        if self.hosts.endswith('.yml') or self.hosts.endswith('.yaml'):
            if not Path(self.hosts).exists():
                print(f"{AnsiColors.FAIL}❌ Inventory file not found: {self.hosts}{AnsiColors.ENDC}")
                return False
        
        return True


class AnsibleRunner:
    """Execute Ansible playbooks"""
    
    def __init__(self, config: DeploymentConfig):
        self.config = config
        
    def build_command(self) -> List[str]:
        """Build ansible-playbook command"""
        cmd = [
            "ansible-playbook",
            "-i", self.config.hosts,
            str(self.config.playbook_file),
            "-u", self.config.user,
            "--port", str(self.config.port),
        ]
        
        # Add verbosity
        if self.config.verbose:
            cmd.append("-vvv")
        
        # Add tags
        if self.config.tags:
            cmd.extend(["--tags", self.config.tags])
        
        if self.config.skip_tags:
            cmd.extend(["--skip-tags", self.config.skip_tags])
        
        # Add dry-run
        if self.config.dry_run:
            cmd.append("--check")
        
        # Add check mode
        if self.config.check_mode:
            cmd.append("--check")
        
        # Add extra vars
        extra_vars = f"env={self.config.env}"
        cmd.extend(["-e", extra_vars])
        
        return cmd
    
    def run(self) -> int:
        """Execute ansible-playbook"""
        cmd = self.build_command()
        
        print(f"{AnsiColors.HEADER}🚀 Anaconda MVP Deployment{AnsiColors.ENDC}")
        print(f"{AnsiColors.BOLD}Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{AnsiColors.ENDC}")
        print("")
        
        print(f"{AnsiColors.OKCYAN}📋 Configuration:{AnsiColors.ENDC}")
        print(f"  Hosts: {self.config.hosts}")
        print(f"  User: {self.config.user}")
        print(f"  Port: {self.config.port}")
        print(f"  Environment: {self.config.env}")
        print(f"  Dry run: {self.config.dry_run}")
        print(f"  Check mode: {self.config.check_mode}")
        print("")
        
        print(f"{AnsiColors.OKCYAN}🔧 Command:{AnsiColors.ENDC}")
        print(f"  {' '.join(cmd)}")
        print("")
        
        if not self.config.dry_run and not self.config.check_mode:
            response = input(f"{AnsiColors.WARNING}Continue with deployment? (yes/no): {AnsiColors.ENDC}")
            if response.lower() not in ['yes', 'y']:
                print(f"{AnsiColors.FAIL}❌ Deployment cancelled{AnsiColors.ENDC}")
                return 1
        
        print(f"{AnsiColors.OKBLUE}⏳ Running Ansible playbook...{AnsiColors.ENDC}")
        print("")
        
        try:
            result = subprocess.run(cmd, check=False)
            return result.returncode
        except KeyboardInterrupt:
            print(f"\n{AnsiColors.FAIL}❌ Deployment interrupted{AnsiColors.ENDC}")
            return 130
        except FileNotFoundError:
            print(f"{AnsiColors.FAIL}❌ ansible-playbook not found. Install Ansible:${AnsiColors.ENDC}")
            print("  pip install ansible")
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="🐍 Anaconda MVP Deployment Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Deploy to production using inventory file
  python3 deploy.py --hosts infrastructure/inventory.yml --env production
  
  # Deploy to single host
  python3 deploy.py --hosts 192.168.1.100 --user nsadmin --env production
  
  # Dry run (check mode)
  python3 deploy.py --hosts inventory.yml --dry-run
  
  # Deploy only backend
  python3 deploy.py --hosts inventory.yml --tags backend
  
  # Skip web build
  python3 deploy.py --hosts inventory.yml --skip-tags web_build
  
  # Verbose output
  python3 deploy.py --hosts inventory.yml --verbose
        """
    )
    
    parser.add_argument(
        "--hosts", "-i",
        required=True,
        help="Inventory file or host address (e.g., inventory.yml or 192.168.1.100)"
    )
    
    parser.add_argument(
        "--user", "-u",
        default="nsadmin",
        help="SSH user (default: nsadmin)"
    )
    
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=22,
        help="SSH port (default: 22)"
    )
    
    parser.add_argument(
        "--env", "-e",
        default="development",
        choices=["development", "staging", "production"],
        help="Environment (default: development)"
    )
    
    parser.add_argument(
        "--tags", "-t",
        help="Only run tasks with these tags (comma-separated)"
    )
    
    parser.add_argument(
        "--skip-tags",
        help="Skip tasks with these tags (comma-separated)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate deployment without making changes"
    )
    
    parser.add_argument(
        "--check", "-c",
        action="store_true",
        help="Run in check mode (non-destructive)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output (Ansible -vvv)"
    )
    
    args = parser.parse_args()
    
    # Create config
    config = DeploymentConfig(args)
    
    # Validate
    if not config.validate():
        return 1
    
    # Run deployment
    runner = AnsibleRunner(config)
    exit_code = runner.run()
    
    # Print result
    print("")
    if exit_code == 0:
        print(f"{AnsiColors.OKGREEN}✅ Deployment successful!{AnsiColors.ENDC}")
    else:
        print(f"{AnsiColors.FAIL}❌ Deployment failed (exit code: {exit_code}){AnsiColors.ENDC}")
    
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
