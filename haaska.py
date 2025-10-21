#!/usr/bin/env python
# coding: utf-8

# Copyright (c) 2015 Michael Auchter <a@phire.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Home Assistant Alexa Smart Home Skill integration module.

This module provides classes to interact with Home Assistant via its API,
handling configuration and HTTP requests for Alexa smart home events.
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests

logger = logging.getLogger()

DEFAULT_TIMEOUT_SECONDS = 30


class ConfigurationLoader:
    """Loads configuration from a file."""

    @staticmethod
    def load(filename: str) -> dict:
        """Load configuration from a file."""
        try:
            with open(filename, encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in config file {filename}: {e}")


class Configuration:
    """Loads and parses configuration from JSON file or dict.

    Handles default values and type conversions for Home Assistant settings.
    """

    def __init__(self, json: dict) -> None:
        """Initialize configuration from file or dict."""
        self._json = json
        self.url = self.get_url(self.get(["url", "ha_url"]))
        self.ssl_verify = self.get(["ssl_verify", "ha_cert"], True)
        self.bearer_token = self.get(["bearer_token"], "")
        self.ssl_client = self.get(["ssl_client"], "")
        # Convert list to tuple for SSL client cert if provided
        if isinstance(self.ssl_client, list):
            self.ssl_client = tuple(self.ssl_client)
        self.debug = self.get(["debug"], False)

    def get(self, keys: List[str], default: Any = None) -> Any:
        """Retrieve value from config dict using multiple possible keys.

        Args:
            keys (list): List of possible key names to check.
            default: Default value if none of the keys are found.

        Returns:
            The value associated with the first matching key, or default.
        """
        return next((self._json[key] for key in keys if key in self._json), default)

    def get_url(self, url: str) -> str:
        """Normalize Home Assistant base URL.

        Removes '/api' suffix and trailing slashes.

        Args:
            url (str): Raw URL from config.

        Returns:
            str: Normalized base URL.

        Raises:
            ValueError: If URL is missing.
        """
        if not url:
            raise ValueError('Property "url" is missing in config')
        return url.replace("/api", "").rstrip("/")


class SessionFactory:
    """Factory for creating configured requests sessions."""

    @staticmethod
    def create_session(config: Configuration) -> requests.Session:
        """Create a configured requests session for Home Assistant API.

        Args:
            config (Configuration): Configuration object with API settings.

        Returns:
            requests.Session: Configured session ready for API calls.
        """
        session = requests.Session()

        # Set up authentication and headers
        session.headers.update(
            {
                "Authorization": f"Bearer {config.bearer_token}",
                "content-type": "application/json",
                "User-Agent": SessionFactory._get_user_agent(),
            }
        )

        # Configure SSL settings
        session.verify = config.ssl_verify
        session.cert = config.ssl_client

        return session

    @staticmethod
    def _get_user_agent() -> str:
        """Generate a user agent string for requests.

        Returns:
            str: User agent string including AWS region and default requests UA.
        """
        aws_region = os.environ.get("AWS_DEFAULT_REGION", "unknown")
        return f"Home Assistant Alexa Smart Home Skill - {aws_region} - {requests.utils.default_user_agent()}"


class HomeAssistant:
    """Handles HTTP interactions with Home Assistant API."""

    def __init__(self, base_url: str, session: requests.Session) -> None:
        """Initialize the HomeAssistant client.

        Args:
            base_url (str): Base URL for HA instance.
            session (requests.Session, optional): Pre-configured session. If None, creates one.
        """
        self.base_url = base_url
        self.session = session

    def build_url(self, endpoint: str) -> str:
        """Build the full API URL for a given endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., 'states').

        Returns:
            str: The complete URL including base URL and '/api/'.
        """
        return f"{self.base_url}/api/{endpoint}"

    def get(self, endpoint: str) -> Dict[str, Any]:
        """Perform a GET request to the Home Assistant API.

        Args:
            endpoint (str): The API endpoint to query.

        Returns:
            dict: JSON response from the API.

        Raises:
            requests.HTTPError: If the request fails.
        """
        r = self.session.get(self.build_url(endpoint))
        r.raise_for_status()
        return r.json()

    def post(
        self, endpoint: str, event: Dict[str, Any], timeout_seconds: Optional[float] = DEFAULT_TIMEOUT_SECONDS
    ) -> Optional[Dict[str, Any]]:
        """Perform a POST request to the Home Assistant API.

        Args:
            endpoint (str): The API endpoint to post to.
            event (dict): JSON data to send in the request body.
            timeout_seconds (float, optional): Request timeout in seconds. Defaults to DEFAULT_TIMEOUT_SECONDS.

        Returns:
            dict or None: JSON response if waiting, else None.

        Raises:
            requests.HTTPError: If the request fails (when waiting).
        """
        try:
            logger.debug("calling %s with %s", endpoint, event)
            r = self.session.post(
                self.build_url(endpoint), json=event, timeout=timeout_seconds
            )
            r.raise_for_status()
            return r.json()
        except requests.exceptions.ReadTimeout:
            logger.debug("request for %s sent without waiting for response", endpoint)
            return None


def event_handler(event: Dict[str, Any], _context: Any) -> Optional[Dict[str, Any]]:
    """AWS Lambda event handler for Alexa smart home events.

    Loads config, sets up logging, and forwards event to Home Assistant.

    Args:
        event (dict): Alexa event data.
        _context: AWS Lambda context object (unused).

    Returns:
        dict or None: Response from Home Assistant API, or None if timed out.
    """
    config = Configuration(ConfigurationLoader.load("config.json"))
    if config.debug:
        logger.setLevel(logging.DEBUG)
    ha = HomeAssistant(config)
    return ha.post("alexa/smart_home", event)
