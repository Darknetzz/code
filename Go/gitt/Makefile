APP := gitt
VERSION ?= dev
COMMIT ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo none)
BUILD_DATE ?= $(shell date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || powershell -NoProfile -Command "(Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')")
LDFLAGS := -X gitt/internal/version.Version=$(VERSION) -X gitt/internal/version.Commit=$(COMMIT) -X gitt/internal/version.BuildDate=$(BUILD_DATE)

.PHONY: build release test

build:
	go build -o $(APP) .

release:
	go build -ldflags "$(LDFLAGS)" -o $(APP) .

test:
	go test ./...
