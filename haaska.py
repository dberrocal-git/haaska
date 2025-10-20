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

class HomeAssistant:
    """Handles HTTP interactions with Home Assistant API.

    This class manages a requests session configured for Home Assistant,
    including authentication, SSL settings, and API calls.
    """

    def __init__(self, config: "Configuration") -> None:
        """Initialize the HomeAssistant client.

        Args:
            config (Configuration): Configuration object containing API settings.
        """
        self.config = config
        self.session = requests.Session()
        # Set up session headers for authentication and content type
        self.session.headers.update(
            {
                "Authorization": f"Bearer {config.bearer_token}",
                "content-type": "application/json",
                "User-Agent": self.get_user_agent(),
            }
        )
        self.session.verify = config.ssl_verify
        self.session.cert = config.ssl_client

    def build_url(self, endpoint: str) -> str:
        """Build the full API URL for a given endpoint.

        Args:
            endpoint (str): The API endpoint path (e.g., 'states').

        Returns:
            str: The complete URL including base URL and '/api/'.
        """
        return f"{self.config.url}/api/{endpoint}"

    def get_user_agent(self) -> str:
        """Generate a user agent string for requests.

        Returns:
            str: User agent string including AWS region and default requests UA.
        """
        return f"Home Assistant Alexa Smart Home Skill - {os.environ.get('AWS_DEFAULT_REGION')} - {requests.utils.default_user_agent()}"

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


class Configuration:
    """Loads and parses configuration from JSON file or dict.

    Handles default values and type conversions for Home Assistant settings.
    """

    def __init__(
        self, filename: Optional[str] = None, opts_dict: Optional[Dict[str, Any]] = None
    ) -> None:
        """Initialize configuration from file or dict.

        Args:
            filename (str, optional): Path to JSON config file.
            opts_dict (dict, optional): Dict with config options.
        """
        self._json = opts_dict or {}
        if filename:
            try:
                with open(filename, encoding="utf-8") as f:
                    self._json = json.load(f)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in config file {filename}: {e}") from e

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


def event_handler(event: Dict[str, Any], _context: Any) -> Optional[Dict[str, Any]]:
    """AWS Lambda event handler for Alexa smart home events.

    Loads config, sets up logging, and forwards event to Home Assistant.

    Args:
        event (dict): Alexa event data.
        _context: AWS Lambda context object (unused).

    Returns:
        dict or None: Response from Home Assistant API, or None if timed out.
    """
    config = Configuration("config.json")
    if config.debug:
        logger.setLevel(logging.DEBUG)
    ha = HomeAssistant(config)
    return ha.post("alexa/smart_home", event)
