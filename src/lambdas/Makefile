# SAM build target for CommonLayer.
# Bundles common/ (logger, idempotency) + app/ (backend models, services, schemas).
# Lambda runtime adds /opt/ to sys.path, so both packages are importable directly.
#
# NOTE: In container builds, SAM only mounts this directory (src/lambdas/).
# Run `scripts/sam-build.sh` which copies app/ here before `sam build --use-container`.

build-CommonLayer:
	mkdir -p $(ARTIFACTS_DIR)
	cp -r common $(ARTIFACTS_DIR)/
	@if [ -d app ]; then \
		cp -r app $(ARTIFACTS_DIR)/; \
	elif [ -d ../backend/app ]; then \
		cp -r ../backend/app $(ARTIFACTS_DIR)/; \
	else \
		echo "ERROR: app/ not found. Run scripts/sam-build.sh for container builds." && exit 1; \
	fi
