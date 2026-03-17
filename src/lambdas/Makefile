# SAM build target for CommonLayer.
# Bundles app/ (backend models, services, schemas, common utilities).
# Lambda runtime adds /opt/ to sys.path, so app/ is importable directly.
#
# NOTE: In container builds, SAM only mounts this directory (src/lambdas/).
# Run `scripts/sam-build.sh` which copies app/ here before `sam build --use-container`.

MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

build-CommonLayer:
	mkdir -p $(ARTIFACTS_DIR)
	@if [ -d $(MAKEFILE_DIR)/app ]; then \
		cp -r $(MAKEFILE_DIR)/app $(ARTIFACTS_DIR)/; \
	elif [ -d $(MAKEFILE_DIR)/../backend/app ]; then \
		cp -r $(MAKEFILE_DIR)/../backend/app $(ARTIFACTS_DIR)/; \
	else \
		echo "ERROR: app/ not found. Run scripts/sam-build.sh for container builds." && exit 1; \
	fi
	pip install -r $(MAKEFILE_DIR)/pipeline/requirements.txt -t $(ARTIFACTS_DIR)/ --quiet
