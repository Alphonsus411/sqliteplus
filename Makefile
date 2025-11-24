PROFILE_SCENARIO ?= list_tables
PROFILE_TOP ?= 30
PROFILE_FLAGS ?=

.PHONY: profile
profile:
	python tools/profile_sqliteplus.py --scenario $(PROFILE_SCENARIO) --top-n $(PROFILE_TOP) $(PROFILE_FLAGS)
