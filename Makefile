REPO_ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
IMAGE_NAME ?= inkplate10-weather-cal-server
DOCKER_CONTEXT ?= ./server
HOST_PORT ?= 8080
RUN_ARGS ?=

LATEST_TAG := $(shell git -C "$(REPO_ROOT)" describe --tags --abbrev=0 --match 'v[0-9]*' 2>/dev/null || echo v1.3.1)
EXACT_TAG := $(shell git -C "$(REPO_ROOT)" describe --tags --exact-match HEAD 2>/dev/null)
COMMIT_SHA := $(shell git -C "$(REPO_ROOT)" rev-parse --short=7 HEAD 2>/dev/null)

SERVER_VERSION := $(if $(EXACT_TAG),$(EXACT_TAG),$(LATEST_TAG))
SERVER_COMMIT_SHA := $(if $(EXACT_TAG),,$(COMMIT_SHA))

.PHONY: build run release
build:
	@echo "Building $(IMAGE_NAME):$(SERVER_VERSION)"
	docker build \
		--build-arg SERVER_VERSION=$(SERVER_VERSION) \
		--build-arg SERVER_COMMIT_SHA=$(SERVER_COMMIT_SHA) \
		-t $(IMAGE_NAME):$(SERVER_VERSION) \
		$(DOCKER_CONTEXT)

run: build
	@echo "Running $(IMAGE_NAME):$(SERVER_VERSION) on localhost:$(HOST_PORT)"
	docker run --rm -p $(HOST_PORT):8080 $(if $(strip $(RUN_ARGS)),$(RUN_ARGS)) $(IMAGE_NAME):$(SERVER_VERSION)

release: build
	@echo "Release build complete for $(IMAGE_NAME):$(SERVER_VERSION)"