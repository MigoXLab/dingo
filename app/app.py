import argparse
import subprocess
import sys


def run_electron_app():
    parser = argparse.ArgumentParser(description='Run Electron app with optional input path')
    parser.add_argument('--input', type=str, help='Input path for the Electron app')
    args = parser.parse_args()

    command = ['npm', 'run', 'dev']
    if args.input:
        command.extend(['--', '--input', args.input])

    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running Electron app: {e}")
        sys.exit(1)


if __name__ == '__main__':
    run_electron_app()
