"""
Pi0 Client Policy Wrapper (runs in DROID Conda environment)

This module provides a client interface for communicating with the Pi0 inference server.
Can be used as a replacement for PolicyWrapper in the DROID evaluation pipeline.

Usage:
    from droid.evaluation.pi0_client import Pi0ClientPolicy
    
    policy = Pi0ClientPolicy(
        server_url="http://localhost:5000",
        prompt="pick up the red cube"
    )
    
    # In evaluation loop
    action = policy.forward(observation)
"""

import base64
import io
import logging
import time
from collections import deque
from typing import Optional

import cv2
import numpy as np
import requests
from PIL import Image

from droid.data_processing.timestep_processing import TimestepProcesser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def encode_image(image: np.ndarray) -> str:
    """Encode numpy image to base64 string."""
    # Ensure image is uint8
    if image.dtype != np.uint8:
        if np.issubdtype(image.dtype, np.floating):
            image = (255 * image).astype(np.uint8)
        else:
            image = image.astype(np.uint8)
    
    # Convert to PIL and encode as PNG
    pil_image = Image.fromarray(image)
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


class Pi0ClientPolicy:
    """
    Pi0 Client Policy Wrapper
    
    Communicates with Pi0 inference server via HTTP REST API.
    Provides an interface compatible with PolicyWrapper.
    
    Required inputs:
        - RGB images (exterior camera, wrist camera)
        - Robot state (joint positions, gripper position)
    
    Optional inputs:
        - Language prompt (task description)
    """
    
    def __init__(
        self,
        server_url: str = "http://localhost:5000",
        prompt: str = "",
        timestep_filtering_kwargs: Optional[dict] = None,
        image_transform_kwargs: Optional[dict] = None,
        image_size: int = 224,
        timeout: float = 30.0,
        action_chunk_size: int = 50,  # Pi0 returns chunks of actions
        use_action_chunking: bool = True,
    ):
        """
        Initialize Pi0 client
        
        Args:
            server_url: Pi0 server URL
            prompt: (Optional) Task description / language instruction
            timestep_filtering_kwargs: Timestep filtering parameters
            image_transform_kwargs: Image transform parameters
            image_size: Image size for RGB cameras
            timeout: HTTP request timeout in seconds
            action_chunk_size: Action chunk size
            use_action_chunking: Whether to use action chunking
        """
        self.server_url = server_url.rstrip('/')
        self.prompt = prompt
        self.image_size = image_size
        self.timeout = timeout
        self.action_chunk_size = action_chunk_size
        self.use_action_chunking = use_action_chunking
        
        # Initialize timestep processor
        if timestep_filtering_kwargs is None:
            timestep_filtering_kwargs = {
                "action_space": "cartesian_velocity",
                "gripper_action_space": "velocity",
                "robot_state_keys": ["cartesian_position", "gripper_position", "joint_positions"],
            }
        
        if image_transform_kwargs is None:
            image_transform_kwargs = {
                "remove_alpha": True,
                "bgr_to_rgb": True,
                "to_tensor": False,
                "augment": False,
            }
        
        self.timestep_processor = TimestepProcesser(
            ignore_action=True,
            **timestep_filtering_kwargs,
            image_transform_kwargs=image_transform_kwargs
        )
        
        # Action chunking buffer
        self.action_buffer = deque()
        self.chunk_index = 0
        
        # Check server connection
        self._check_server_health()
    
    def _check_server_health(self):
        """Check server health status"""
        try:
            response = requests.get(
                f"{self.server_url}/health",
                timeout=5.0
            )
            if response.status_code == 200:
                info = response.json()
                logger.info(f"Connected to Pi0 server: {info}")
            else:
                logger.warning(f"Server health check returned: {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Cannot connect to Pi0 server at {self.server_url}: {e}")
            logger.warning("Make sure the server is running!")
    
    def _prepare_observation(self, observation: dict) -> dict:
        """
        Prepare observation data to send to server
        
        Args:
            observation: Raw observation in DROID format
            
        Returns:
            Observation dict in Pi0 format
        """
        # Process timestep
        timestep = {"observation": observation}
        processed = self.timestep_processor.forward(timestep)
        
        # Extract images
        camera_images = processed["observation"]["camera"]["image"]
        
        # Get exterior and wrist camera images
        # Exterior camera (varied_camera) - use first left one
        if "varied_camera" in camera_images and len(camera_images["varied_camera"]) > 0:
            exterior_image = camera_images["varied_camera"][0]
        else:
            exterior_image = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        
        # Wrist camera (hand_camera) - use left one
        if "hand_camera" in camera_images and len(camera_images["hand_camera"]) > 0:
            wrist_image = camera_images["hand_camera"][0]
        else:
            wrist_image = np.zeros((self.image_size, self.image_size, 3), dtype=np.uint8)
        
        # Ensure images are in correct format (H, W, C) and uint8
        exterior_image = self._process_image(exterior_image)
        wrist_image = self._process_image(wrist_image)
        
        # Resize images
        exterior_image = cv2.resize(exterior_image, (self.image_size, self.image_size))
        wrist_image = cv2.resize(wrist_image, (self.image_size, self.image_size))
        
        # Extract robot state
        robot_state = observation.get("robot_state", {})
        joint_positions = np.array(robot_state.get("joint_positions", np.zeros(7)), dtype=np.float32)
        gripper_position = np.array([robot_state.get("gripper_position", 0.0)], dtype=np.float32)
        
        # Build request payload with required inputs (RGB images + robot state)
        payload = {
            # RGB images (required)
            "observation/exterior_image_1_left": encode_image(exterior_image),
            "observation/wrist_image_left": encode_image(wrist_image),
            # Robot state (required)
            "observation/joint_position": joint_positions.tolist(),
            "observation/gripper_position": gripper_position.tolist(),
        }
        
        # Language prompt (optional)
        if self.prompt:
            payload["prompt"] = self.prompt
        
        return payload
    
    def _process_image(self, image: np.ndarray) -> np.ndarray:
        """Process image format"""
        # If tensor (C, H, W) format, convert to (H, W, C)
        if len(image.shape) == 3 and image.shape[0] == 3:
            image = np.transpose(image, (1, 2, 0))
        
        # If floating point, convert to uint8
        if np.issubdtype(image.dtype, np.floating):
            image = (255 * image).astype(np.uint8)
        
        return image
    
    def _call_server(self, payload: dict) -> np.ndarray:
        """
        Call inference server
        
        Args:
            payload: Request data
            
        Returns:
            Action chunk (shape: [chunk_size, action_dim])
        """
        try:
            start_time = time.time()
            
            response = requests.post(
                f"{self.server_url}/infer",
                json=payload,
                timeout=self.timeout
            )
            
            elapsed = time.time() - start_time
            logger.debug(f"Inference took {elapsed:.3f}s")
            
            if response.status_code != 200:
                error_msg = response.json().get("error", "Unknown error")
                raise RuntimeError(f"Server error: {error_msg}")
            
            result = response.json()
            actions = np.array(result["actions"], dtype=np.float32)
            
            logger.debug(f"Received action chunk with shape: {actions.shape}")
            return actions
            
        except requests.exceptions.Timeout:
            raise RuntimeError(f"Request timeout after {self.timeout}s")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Request failed: {e}")
    
    def forward(self, observation: dict) -> np.ndarray:
        """
        Get next action
        
        Args:
            observation: Observation in DROID format
            
        Returns:
            Single action vector (shape: [action_dim])
        """
        if self.use_action_chunking and len(self.action_buffer) > 0:
            # Return next action from buffer
            return self.action_buffer.popleft()
        
        # Prepare observation data
        payload = self._prepare_observation(observation)
        
        # Call server to get action chunk
        action_chunk = self._call_server(payload)
        
        if self.use_action_chunking:
            # Add chunk to buffer
            for i in range(len(action_chunk)):
                self.action_buffer.append(action_chunk[i])
            
            # Return first action
            return self.action_buffer.popleft()
        else:
            # Only return first action
            return action_chunk[0]
    
    def reset(self):
        """Reset policy state"""
        self.action_buffer.clear()
        self.chunk_index = 0
        
        # Notify server to reset
        try:
            requests.post(f"{self.server_url}/reset", timeout=5.0)
        except requests.exceptions.RequestException:
            pass  # Reset failure is not critical
    
    def set_prompt(self, prompt: str):
        """Update task description"""
        self.prompt = prompt
        # Clear action buffer when prompt is updated
        self.action_buffer.clear()


class Pi0ClientPolicyWrapper:
    """
    Pi0 client wrapper compatible with PolicyWrapperRobomimic
    
    Can directly replace wrapped_policy in eval_launcher_robomimic.py
    """
    
    def __init__(
        self,
        server_url: str = "http://localhost:5000",
        prompt: str = "",
        timestep_filtering_kwargs: Optional[dict] = None,
        image_transform_kwargs: Optional[dict] = None,
        frame_stack: int = 1,
        eval_mode: bool = True,
        **kwargs
    ):
        """
        Initialize wrapper
        
        Args:
            server_url: Pi0 server URL
            prompt: Task description
            timestep_filtering_kwargs: Timestep filtering parameters
            image_transform_kwargs: Image transform parameters
            frame_stack: Number of frame stacks (currently unused, for interface compatibility)
            eval_mode: Evaluation mode (for interface compatibility)
        """
        self.client = Pi0ClientPolicy(
            server_url=server_url,
            prompt=prompt,
            timestep_filtering_kwargs=timestep_filtering_kwargs,
            image_transform_kwargs=image_transform_kwargs,
            **kwargs
        )
        self.frame_stack = frame_stack
    
    def forward(self, observation: dict) -> np.ndarray:
        """Get action"""
        return self.client.forward(observation)
    
    def reset(self):
        """Reset policy"""
        self.client.reset()


def test_client():
    """Test client connection"""
    client = Pi0ClientPolicy(
        server_url="http://localhost:5000",
        prompt="pick up the red cube"
    )
    
    # Create fake observation
    fake_obs = {
        "robot_state": {
            "joint_positions": np.random.rand(7).tolist(),
            "gripper_position": 0.5,
            "cartesian_position": np.random.rand(6).tolist(),
        },
        "camera": {
            "image": {
                "hand_camera": [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)],
                "varied_camera": [np.random.randint(0, 255, (224, 224, 3), dtype=np.uint8)],
            }
        }
    }
    
    print("Testing inference...")
    action = client.forward(fake_obs)
    print(f"Received action: {action.shape}")
    print(f"Action values: {action}")


if __name__ == "__main__":
    test_client()
