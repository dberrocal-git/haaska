import os

import pytest

from haaska import Configuration, HomeAssistant, SessionFactory


@pytest.fixture
def configuration():
    return Configuration(
        {
            "url": "http://localhost:8123",
            "bearer_token": "",
            "debug": False,
            "ssl_verify": True,
            "ssl_client": [],
        }
    )


@pytest.fixture
def home_assistant(configuration):
    return HomeAssistant(configuration.url, SessionFactory.create_session(configuration))


def test_ha_build_url(home_assistant):
    url = home_assistant.build_url("test")
    assert url == "http://localhost:8123/api/test"


def test_session_factory_user_agent(configuration):
    os.environ["AWS_DEFAULT_REGION"] = "test"
    user_agent = SessionFactory.create_session(configuration).headers["User-Agent"]
    assert user_agent.startswith("Home Assistant Alexa Smart Home Skill - test - python-requests/")


def test_config_get(configuration):
    assert configuration.get(["debug"]) is False
    assert configuration.get(["test"]) is None
    assert configuration.get(["test"], default="default") == "default"


def test_config_get_url(configuration):
    test_urls = ["http://hass.example.com:8123", "http://hass.example.app"]
    for expected_url in test_urls:
        assert configuration.get_url(expected_url + "/") == expected_url
        assert configuration.get_url(expected_url + "/api") == expected_url
        assert configuration.get_url(expected_url + "/api/") == expected_url
