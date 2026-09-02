"""Every Sibyl `category` string MEMORA writes, in one place.

Sibyl retrieval is FTS5 keyword matching plus exact (category, name) lookup --
there is no embedding model. These strings are the retrieval surface itself,
not internal labels, so they stay lowercase, singular and search-friendly.
"""

# WARM entities -- current state, one row per (tenant, kind, name)
KIND_MEDICATION = "medication"
KIND_ALLERGY = "allergy"
KIND_DIAGNOSIS = "diagnosis"
KIND_PROCEDURE = "procedure"
KIND_LAB_TREND = "lab_trend"
KIND_CARE_PHASE = "care_phase"

ALL_KINDS = (
    KIND_MEDICATION,
    KIND_ALLERGY,
    KIND_DIAGNOSIS,
    KIND_PROCEDURE,
    KIND_LAB_TREND,
    KIND_CARE_PHASE,
)

# Entity `status` column values. This is a real indexed column on the Sibyl
# row (set via set_entity(..., status=...)), which is what makes
# list_facts(status=STATUS_CONTRAINDICATED) an actual query rather than a
# full scan plus a body inspection.
STATUS_ACTIVE = "active"
STATUS_DISCONTINUED = "discontinued"
STATUS_CONTRAINDICATED = "contraindicated"
STATUS_DOCUMENTED = "documented"
STATUS_PERFORMED = "performed"
STATUS_RESOLVED = "resolved"

# HOT state keys
STATE_KEY_ACTIVE_SITUATION = "active_situation"

# REFERENCE document keys
REF_KEY_POLICY = "clinical_policy"
REF_KEY_PROTOCOL_PREFIX = "protocol"
