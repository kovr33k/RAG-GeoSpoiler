import os
import subprocess
import sys
import unittest
from pathlib import Path


class NoNetworkRuleTests(unittest.TestCase):
    def test_no_network_env_blocks_socket_connections(self):
        env = os.environ.copy()
        env["GEOSPOILER_NO_NETWORK"] = "1"
        env["PYTHONPATH"] = str(Path(__file__).parent)
        code = (
            "import socket\n"
            "try:\n"
            "    socket.create_connection(('example.com', 80), timeout=0.1)\n"
            "except Exception as exc:\n"
            "    print(type(exc).__name__)\n"
            "else:\n"
            "    raise SystemExit('network was not blocked')\n"
        )

        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=Path(__file__).parent,
            env=env,
            text=True,
            capture_output=True,
            check=True,
        )

        self.assertIn("NetworkBlockedError", result.stdout)


if __name__ == "__main__":
    unittest.main()
