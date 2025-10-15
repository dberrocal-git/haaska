SHELL := /bin/bash

# Function name in AWS Lambda:
FUNCTION_NAME=haaska

BUILD_DIR=build

# Python 3.13 configuration
PYTHON=python
PIP=pip3

haaska.zip: haaska.py config/*
	mkdir -p $(BUILD_DIR)
	cp $^ $(BUILD_DIR)
	$(PIP) install -t $(BUILD_DIR) requests
	chmod 755 $(BUILD_DIR)/haaska.py
	cd $(BUILD_DIR); zip ../$@ -r *

.PHONY: all clean zip deploy discover sample_config modernize_config

all: haaska.zip

.PHONY: deploy
deploy: haaska.zip
	aws lambda update-function-configuration \
		--function-name $(FUNCTION_NAME) \
		--handler haaska.event_handler
	aws lambda update-function-code \
		--function-name $(FUNCTION_NAME) \
		--zip-file fileb://$<

DISCOVERY_PAYLOAD:='                                \
{                                                         \
  "directive": {                                          \
    "header": {                                           \
      "namespace": "Alexa.Discovery",                     \
      "name": "Discover",                                 \
      "payloadVersion": "3",                              \
      "messageId": "1bd5d003-31b9-476f-ad03-71d471922820" \
    },                                                    \
    "payload": {                                          \
      "scope": {                                          \
        "type": "BearerToken",                            \
        "token": "access-token-from-skill"                \
      }                                                   \
    }                                                     \
  }                                                       \
}'

.PHONY: discover
discover:
	@aws lambda invoke \
		--function-name $(FUNCTION_NAME) \
		--payload ${DISCOVERY_PAYLOAD} \
		/dev/fd/3 3>&1 >/dev/null | jq '.'


.PHONY: clean
clean:
	rm -rf $(BUILD_DIR) haaska.zip

.PHONY: sample_config
sample_config:
	$(PYTHON) -c 'from haaska import Configuration; print(Configuration().dump())' > config/config.json.sample

.PHONY: modernize_config
modernize_config: config/config.json
	@$(PYTHON) -c 'from haaska import Configuration; print(Configuration("config/config.json").dump())' > config/config.json.modernized
	@echo Generated config/config.json.modernized from your existing config/config.json
	@echo Inspect that file and replace config/config.json with it to update your configuration

.PHONY: all clean zip

PACKAGE_NAME = haaska
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
ZIP_FILE = $(PACKAGE_NAME)-$(VERSION).zip

all: zip

zip: clean
	@echo "Creating $(ZIP_FILE)..."
	@zip -r $(ZIP_FILE) . -x "*.git*" "*.zip" "*.pyc" "__pycache__/*" "*.md" ".github/*"
	@echo "Package created: $(ZIP_FILE)"

clean:
	@echo "Cleaning up..."
	@rm -f $(PACKAGE_NAME)-*.zip
	@echo "Clean complete"
