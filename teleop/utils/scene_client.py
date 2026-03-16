"""
Scene Control API Client

Used by xr_teleoperate to communicate with unitree_sim_isaaclab's Scene API server.
Sends scene control commands after recording episodes:

  - On save: request "load next scene"
  - On discard: request "reset current scene"
  - Handle "all tasks completed" response

Usage:
    client = SceneClient("http://192.168.1.100:8200")

    # After saving an episode
    result = client.next_scene()
    if result.all_completed:
        print("All tasks done!")

    # After discarding an episode
    result = client.reset_scene()
"""

import logging
import time
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger("scene_client")


@dataclass
class SceneResponse:
    """Parsed response from the Scene API server."""
    success: bool
    message: str
    task_num: int
    current_scene_index: int
    all_completed: bool
    task_id: str = ""
    instructions: dict = None


@dataclass
class SceneStatus:
    """Parsed status from the Scene API server."""
    task_num: int
    current_scene_index: int
    total_scenes: int
    scene_json_path: str
    all_completed: bool
    state: str  # "ready", "busy", "finished"
    task_id: str = ""
    instructions: dict = None


class SceneClient:
    """HTTP client for the Scene Control API.

    Args:
        server_url: Base URL of the scene server (e.g., "http://localhost:8200").
        timeout: Request timeout in seconds. Scene transitions may take time,
                 so this should be generous (default: 60s).
        retry_count: Number of retries for transient failures.
        retry_delay: Seconds between retries.
    """

    def __init__(
        self,
        server_url: str = "http://localhost:8200",
        timeout: float = 60.0,
        retry_count: int = 2,
        retry_delay: float = 1.0,
    ):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        self._session = requests.Session()

    def is_available(self) -> bool:
        """Check if the scene server is reachable."""
        try:
            resp = self._session.get(
                f"{self.server_url}/scene/status",
                timeout=5.0,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def get_status(self) -> Optional[SceneStatus]:
        """Get current scene status from the server."""
        try:
            resp = self._session.get(
                f"{self.server_url}/scene/status",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            return SceneStatus(
                task_num=data["task_num"],
                current_scene_index=data["current_scene_index"],
                total_scenes=data["total_scenes"],
                scene_json_path=data["scene_json_path"],
                all_completed=data["all_completed"],
                state=data["state"],
                task_id=data.get("task_id", ""),
                instructions=data.get("instructions", {}),
            )
        except requests.RequestException as e:
            logger.error(f"Failed to get scene status: {e}")
            return None

    def reset_scene(self) -> SceneResponse:
        """Request the server to reset the current scene to original positions.

        Called after an episode is discarded.
        """
        return self._post("/scene/reset")

    def next_scene(self) -> SceneResponse:
        """Request the server to load the next scene.

        Called after an episode is saved.

        Returns:
            SceneResponse with all_completed=True if no more scenes remain.
        """
        return self._post("/scene/next")

    def _post(self, endpoint: str) -> SceneResponse:
        """Send a POST request with retry logic."""
        url = f"{self.server_url}{endpoint}"
        last_error = None

        for attempt in range(1 + self.retry_count):
            try:
                resp = self._session.post(url, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                result = SceneResponse(
                    success=data["success"],
                    message=data["message"],
                    task_num=data["task_num"],
                    current_scene_index=data["current_scene_index"],
                    all_completed=data["all_completed"],
                    task_id=data.get("task_id", ""),
                    instructions=data.get("instructions", {}),
                )
                if result.success:
                    logger.info(f"[SceneClient] {endpoint}: {result.message}")
                else:
                    logger.warning(f"[SceneClient] {endpoint} failed: {result.message}")
                return result

            except requests.RequestException as e:
                last_error = e
                if attempt < self.retry_count:
                    logger.warning(
                        f"[SceneClient] {endpoint} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {self.retry_delay}s..."
                    )
                    time.sleep(self.retry_delay)

        # All retries exhausted
        logger.error(f"[SceneClient] {endpoint} failed after {1 + self.retry_count} attempts: {last_error}")
        return SceneResponse(
            success=False,
            message=f"Connection failed: {last_error}",
            task_num=-1,
            current_scene_index=-1,
            all_completed=False,
        )

    def close(self):
        """Close the HTTP session."""
        self._session.close()
