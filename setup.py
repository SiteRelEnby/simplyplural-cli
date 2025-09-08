#!/usr/bin/env python3
"""
Quick setup script for Simply Plural CLI

This script helps you get started with the Simply Plural CLI by:
1. Checking dependencies
2. Testing basic functionality
3. Running the configuration wizard
"""

import sys
import subprocess
from pathlib import Path

def run_command(cmd, description):
    """Run a command and report results"""
    print(f"-> {description}...")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        if result.returncode == 0:
            print(f"  [OK] Success")
            return True
        else:
            print(f"  [FAIL] Failed: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        return False

def main():
    print("Simply Plural CLI Setup")
    print("=" * 50)
    
    # Check if we're in the right directory
    sp_file = Path("sp.py")
    if not sp_file.exists():
        print("Error: sp.py not found in current directory")
        print("Please run this from the simplyplural-cli directory")
        return 1
    
    # 1. Check Python version
    print(f"\n1. Python version: {sys.version.split()[0]}")
    if sys.version_info < (3, 7):
        print("  [FAIL] Python 3.7+ required")
        return 1
    else:
        print("  [OK] Python version OK")
    
    # 2. Install dependencies
    print("\n2. Installing dependencies...")
    if run_command("python -m pip install requests", "Installing requests"):
        print("  [OK] Dependencies installed")
    else:
        print("  [WARN] Failed to install dependencies. Try manually:")
        print("    python -m pip install requests")
        return 1
    
    # 3. Test basic functionality
    print("\n3. Testing CLI...")
    if run_command("python sp.py --help", "Testing CLI help"):
        print("  [OK] CLI is working")
    else:
        print("  [FAIL] CLI test failed")
        return 1
    
    # 4. Run configuration
    print("\n4. Configuration setup")
    print("The CLI will now guide you through setting up your API token.")
    print("You'll need to:")
    print("  1. Open Simply Plural app")
    print("  2. Go to Settings -> Privacy & Security -> API Tokens")
    print("  3. Create a token with permissions: Read members, Read switches, Write switches, Read front")
    
    proceed = input("\nReady to configure? (y/N): ").strip().lower()
    if proceed.startswith('y'):
        try:
            subprocess.run([sys.executable, "sp.py", "config", "--setup"], check=False)
        except KeyboardInterrupt:
            print("\nConfiguration cancelled.")
    else:
        print("\nConfiguration skipped. Run 'python sp.py config --setup' when ready.")
    
    # 5. Success message
    print("\n" + "=" * 50)
    print("Setup complete!")
    print("\nTry these commands:")
    print("  python sp.py --help           # Show all commands")
    print("  python sp.py fronting         # Show current fronters")
    print("  python sp.py members          # List all members")
    print("  python sp.py switch <name>    # Register a switch")
    
    print("\nTo use 'sp' instead of 'python sp.py':")
    print("  1. Copy sp.py to a directory in your PATH (e.g., ~/bin)")
    print("  2. Make it executable: chmod +x sp.py")
    print("  3. Rename it: mv sp.py sp")
    
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(1)
