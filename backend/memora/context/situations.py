"""Clinical situations, clinician roles, and what each situation cares about.

SITUATION_FOCUS is the retrieval "compiler" table: adding a new situation means
adding one row here, not new ad-hoc query logic somewhere downstream. Keeping it
declarative is what makes compile_plan a pure function, and therefore what makes
"the same patient memory yields a different relevant subset per situation" true
by construction rather than true only in the demo script.
"""

from enum import Enum

from memora.ontology.events import (
    EVENT_ADVERSE_REACTION,
    EVENT_COMPLICATION,
    EVENT_DIAGNOSIS_MADE,
    EVENT_LAB_RESULT,
    EVENT_MEDICATION_ADMINISTERED,
    EVENT_MEDICATION_DISCONTINUED,
    EVENT_PROCEDURE_PERFORMED,
)
from memora.ontology.kinds import (
    KIND_ALLERGY,
    KIND_DIAGNOSIS,
    KIND_LAB_TREND,
    KIND_MEDICATION,
    KIND_PROCEDURE,
)


class Situation(str, Enum):
    ICU_TO_WARD = "icu_to_ward"
    PRE_OPERATIVE = "pre_operative"
    DISCHARGE = "discharge"


class ClinicianRole(str, Enum):
    WARD_PHYSICIAN = "ward_physician"
    SURGEON = "surgeon"
    ICU_PHYSICIAN = "icu_physician"


class SituationFocus:
    """One row of the focus table. Tuples, not lists, so a compiled plan is
    hashable and comparable -- the determinism test asserts plan equality."""

    __slots__ = ("event_types", "kinds", "task")

    def __init__(self, kinds: tuple[str, ...], event_types: tuple[str, ...], task: str):
        self.kinds = kinds
        self.event_types = event_types
        self.task = task


SITUATION_FOCUS: dict[Situation, SituationFocus] = {
    Situation.ICU_TO_WARD: SituationFocus(
        kinds=(KIND_MEDICATION, KIND_ALLERGY, KIND_LAB_TREND, KIND_DIAGNOSIS),
        event_types=(
            EVENT_ADVERSE_REACTION,
            EVENT_MEDICATION_DISCONTINUED,
            EVENT_LAB_RESULT,
            EVENT_COMPLICATION,
        ),
        task="medication_reconciliation",
    ),
    Situation.PRE_OPERATIVE: SituationFocus(
        kinds=(KIND_ALLERGY, KIND_PROCEDURE, KIND_MEDICATION),
        event_types=(
            EVENT_ADVERSE_REACTION,
            EVENT_COMPLICATION,
            EVENT_PROCEDURE_PERFORMED,
        ),
        task="pre_operative_review",
    ),
    Situation.DISCHARGE: SituationFocus(
        kinds=(KIND_DIAGNOSIS, KIND_MEDICATION, KIND_PROCEDURE),
        event_types=(
            EVENT_DIAGNOSIS_MADE,
            EVENT_MEDICATION_ADMINISTERED,
            EVENT_PROCEDURE_PERFORMED,
        ),
        task="continuity_of_care",
    ),
}
