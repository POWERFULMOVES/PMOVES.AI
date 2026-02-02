#!/usr/bin/env python3
"""
Example Tool Implementation Template

This module demonstrates the expected structure and documentation patterns
for tools within PMOVES.AI skills.

Based on PMOVES-BoTZ and PMOVES-DoX tool patterns.
"""

import argparse
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ExampleTool:
    """
    Example tool for demonstrating skill structure.

    This class shows the expected patterns for tool implementation including:
    - Proper docstrings with Google style
    - Type hints for all parameters
    - Error handling with specific exceptions
    - Logging at appropriate levels
    - Configuration via environment variables or CLI args

    Attributes:
        config_path: Path to configuration file
        dry_run: If True, don't make actual changes

    Example:
        >>> tool = ExampleTool(config_path="config.yaml")
        >>> result = tool.execute(param1="value")
        >>> print(result)
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        dry_run: bool = False
    ):
        """
        Initialize the ExampleTool.

        Args:
            config_path: Optional path to configuration file
            dry_run: If True, simulate actions without making changes

        Raises:
            FileNotFoundError: If config_path is provided but file doesn't exist
            ValueError: If configuration is invalid
        """
        self.config_path = Path(config_path) if config_path else None
        self.dry_run = dry_run
        self.config: Dict[str, Any] = {}

        if self.config_path:
            self._load_config()

    def _load_config(self) -> None:
        """
        Load configuration from file.

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config YAML is invalid
        """
        if not self.config_path or not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            import yaml
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from {self.config_path}")
        except ImportError:
            logger.warning("PyYAML not installed, skipping config load")
        except Exception as e:
            raise ValueError(f"Failed to load config: {e}")

    def execute(
        self,
        param1: str,
        param2: Optional[int] = None,
        verbose: bool = False
    ) -> Dict[str, Any]:
        """
        Execute the primary tool operation.

        This method demonstrates the expected structure for tool execution:
        - Parameter validation
        - Dry run support
        - Comprehensive error handling
        - Structured return value

        Args:
            param1: Required parameter for the operation
            param2: Optional numeric parameter
            verbose: Enable verbose output

        Returns:
            Dictionary containing:
                - success (bool): Whether operation succeeded
                - result (Any): Primary result data
                - metadata (dict): Additional information

        Raises:
            ValueError: If required parameters are invalid
            RuntimeError: If operation fails in non-dry-run mode

        Example:
            >>> tool = ExampleTool()
            >>> result = tool.execute(param1="test", param2=42)
            >>> print(result['success'])
            True
        """
        # Validate inputs
        if not param1 or not isinstance(param1, str):
            raise ValueError("param1 must be a non-empty string")

        if param2 is not None and param2 < 0:
            raise ValueError("param2 must be non-negative")

        if verbose:
            logger.info(f"Executing with param1={param1}, param2={param2}")

        # Dry run mode
        if self.dry_run:
            logger.info("DRY RUN: Would execute operation")
            return {
                "success": True,
                "result": f"Would process: {param1}",
                "metadata": {
                    "dry_run": True,
                    "param1": param1,
                    "param2": param2
                }
            }

        # Actual execution
        try:
            result = self._do_work(param1, param2)

            return {
                "success": True,
                "result": result,
                "metadata": {
                    "dry_run": False,
                    "config_path": str(self.config_path) if self.config_path else None
                }
            }

        except Exception as e:
            logger.error(f"Execution failed: {e}")
            raise RuntimeError(f"Tool execution failed: {e}") from e

    def _do_work(self, param1: str, param2: Optional[int]) -> str:
        """
        Internal method that performs the actual work.

        Args:
            param1: Primary parameter
            param2: Optional secondary parameter

        Returns:
            Result string

        Raises:
            RuntimeError: If work fails
        """
        # Simulate work
        logger.debug(f"Processing param1={param1}")

        if param2:
            logger.debug(f"Using param2={param2}")
            return f"Processed {param1} with value {param2}"

        return f"Processed {param1}"

    def validate(self) -> bool:
        """
        Validate tool configuration and environment.

        Returns:
            True if validation passes

        Raises:
            ValueError: If validation fails
        """
        # Check configuration
        if self.config_path and not self.config_path.exists():
            raise ValueError(f"Config file missing: {self.config_path}")

        # Check environment
        # env_var = os.environ.get("REQUIRED_ENV")
        # if not env_var:
        #     raise ValueError("REQUIRED_ENV not set")

        logger.info("Validation passed")
        return True


def main():
    """
    CLI entry point for the tool.

    This function demonstrates the expected CLI interface:
    - Argument parsing with argparse
    - Help documentation
    - Error handling with exit codes
    - JSON output for programmatic use

    Exit codes:
        0: Success
        1: Execution error
        2: Configuration error
    """
    parser = argparse.ArgumentParser(
        description="Example tool for PMOVES.AI skills",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  %(prog)s --param1 value

  # With optional parameter
  %(prog)s --param1 value --param2 42

  # Dry run
  %(prog)s --param1 value --dry-run

  # JSON output
  %(prog)s --param1 value --output json
        """
    )

    # Required arguments
    parser.add_argument(
        '--param1',
        required=True,
        help='Required parameter for tool execution'
    )

    # Optional arguments
    parser.add_argument(
        '--param2',
        type=int,
        default=None,
        help='Optional numeric parameter'
    )

    parser.add_argument(
        '--config',
        type=str,
        default=None,
        help='Path to configuration file'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate execution without making changes'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )

    parser.add_argument(
        '--output',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )

    args = parser.parse_args()

    # Create tool instance
    try:
        tool = ExampleTool(
            config_path=args.config,
            dry_run=args.dry_run
        )
        tool.validate()

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Configuration error: {e}")
        return 2

    # Execute tool
    try:
        result = tool.execute(
            param1=args.param1,
            param2=args.param2,
            verbose=args.verbose
        )

        if args.output == 'json':
            print(json.dumps(result, indent=2))
        else:
            if result['success']:
                print(f"Success: {result['result']}")
            else:
                print(f"Failed: {result.get('error', 'Unknown error')}")

        return 0

    except Exception as e:
        logger.error(f"Execution error: {e}")
        if args.output == 'json':
            print(json.dumps({
                "success": False,
                "error": str(e)
            }, indent=2))
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
