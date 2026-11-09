# pmoves/mk/image-staleness.mk — Image staleness ratchet targets
# ============================================================================
# The fleet's images go stale silently when nothing rebuilds them.
# `pmoves/images.yaml` declares the build matrix and
# `.github/workflows/build-images.yml` builds it; this ratchet asserts that
# every entry in that matrix still has (a) the fields this ratchet REQUIRES
# (`name` and `dockerfile` -- the builder's own reads are `matrix.name` for
# the tag and `matrix.dockerfile` for the file; `image` is never read by the
# build and `context` is a fallback the repo-backed entries never reach),
# (b) build inputs that exist in the tree, and (c) a build path that does
# not need a human to click. Read-only, zero network, stdlib only.
#
#   make -C pmoves image-staleness-ratchet         # human-readable
#   make -C pmoves image-staleness-ratchet-json    # machine-readable
#   make -C pmoves image-staleness-test            # pytest the ratchet itself
#
# Exit 1 = at least one image is DRIFTED (unbuildable / no rebuild path).
# UNDECIDED (a submodule that is not checked out here) is reported but does
# not fail: "could not check" is not "broken".

.PHONY: image-staleness-ratchet image-staleness-ratchet-json image-staleness-test

image-staleness-ratchet: ## Assert every image in pmoves/images.yaml has build inputs and a non-manual rebuild path (no network)
	@echo "🔒 Image-staleness ratchet..."
	@$(PYTHON) tools/image_staleness_ratchet.py

image-staleness-ratchet-json: ## Same as image-staleness-ratchet, but JSON output (for CI annotation)
	@$(PYTHON) tools/image_staleness_ratchet.py --json

image-staleness-test: ## Pytest the image-staleness ratchet (regression net for the ratchet itself)
	@$(PYTHON) -m pytest tools/tests/test_image_staleness_ratchet.py -v
