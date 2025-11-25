PROFILE_SCENARIO ?= list_tables
PROFILE_TOP ?= 30
PROFILE_FLAGS ?=
HOTSPOT_SCENARIOS ?=
HOTSPOT_INCLUDE_IO ?=0

.PHONY: profile
profile:
	python tools/profile_sqliteplus.py --scenario $(PROFILE_SCENARIO) --top-n $(PROFILE_TOP) $(PROFILE_FLAGS)

.PHONY: profile-hotspots
profile-hotspots:
	python tools/profile_hotspots.py --top-n $(PROFILE_TOP) $(if $(filter 1,$(HOTSPOT_INCLUDE_IO)),--include-io,) $(foreach scenario,$(HOTSPOT_SCENARIOS),--scenario $(scenario))
