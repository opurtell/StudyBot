from dataclasses import dataclass


@dataclass(frozen=True)
class Base:
    id: str
    display: str
    implies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Endorsement:
    id: str
    display: str
    requires_base: tuple[str, ...] = ()


@dataclass(frozen=True)
class QualificationModel:
    bases: tuple[Base, ...]
    endorsements: tuple[Endorsement, ...] = ()


SOURCE_HIERARCHY_DEFAULTS: tuple[tuple[str, float], ...] = (
    ("guideline", 1.00),
    ("ref_doc", 0.80),
    ("cpd_doc", 0.60),
    ("notability", 0.40),
    ("upload", 0.30),
)


@dataclass(frozen=True)
class Service:
    id: str
    display_name: str
    region: str
    accent_colour: str
    source_url: str
    scope_source_doc: str
    qualifications: QualificationModel
    adapter: str
    category_mapping_doc: str
    source_hierarchy: tuple[tuple[str, float], ...] = SOURCE_HIERARCHY_DEFAULTS
    section_aliases: tuple[tuple[str, str], ...] = ()

    def resolve_section(self, section: str) -> str:
        """Translate a quiz-internal section name to the service's ChromaDB section."""
        return dict(self.section_aliases).get(section, section)

    @property
    def short_name(self) -> str:
        """Short uppercase identifier for citations (e.g. 'ACTAS', 'AT')."""
        return self.id.upper()


REGISTRY: tuple[Service, ...] = (
    Service(
        id="actas",
        display_name="ACT Ambulance Service",
        region="Australian Capital Territory",
        accent_colour="#2D5A54",
        source_url="https://cmg.ambulance.act.gov.au",
        scope_source_doc="Guides/scope-of-practice-actas.md",
        qualifications=QualificationModel(
            bases=(
                Base("AP", "Ambulance Paramedic"),
                Base("ICP", "Intensive Care Paramedic", implies=("AP",)),
            ),
        ),
        adapter="src.python.pipeline.actas",
        category_mapping_doc="Guides/categories-actas.md",
    ),
    Service(
        id="at",
        display_name="Ambulance Tasmania",
        region="Tasmania",
        accent_colour="#005a96",
        source_url="https://cpg.ambulance.tas.gov.au",
        scope_source_doc="Guides/scope-of-practice-at.md",
        qualifications=QualificationModel(
            bases=(
                Base("VAO", "Volunteer Ambulance Officer"),
                Base("PARAMEDIC", "Paramedic"),
            ),
            endorsements=(
                Endorsement("ICP", "Intensive Care Paramedic", requires_base=("PARAMEDIC",)),
                Endorsement("PACER", "PACER", requires_base=("PARAMEDIC",)),
                Endorsement(
                    "CP_ECP",
                    "Community Paramedic / Extended Care Paramedic",
                    requires_base=("PARAMEDIC",),
                ),
            ),
        ),
        adapter="src.python.pipeline.at",
        category_mapping_doc="Guides/categories-at.md",
        section_aliases=(
            ("Cardiac", "Adult Patient Guidelines"),
            ("Trauma", "Adult Patient Guidelines"),
            ("Medical", "Adult Patient Guidelines"),
            ("Respiratory", "Adult Patient Guidelines"),
            ("Airway Management", "Adult Patient Guidelines"),
            ("Obstetric", "Maternity"),
            ("Neurology", "Adult Patient Guidelines"),
            ("Behavioural", "Adult Patient Guidelines"),
            ("Toxicology", "Adult Patient Guidelines"),
            ("Environmental", "Adult Patient Guidelines"),
            ("Pain Management", "Adult Patient Guidelines"),
            ("Palliative Care", "Adult Patient Guidelines"),
            ("HAZMAT", "Adult Patient Guidelines"),
            ("General Care", "Adult Patient Guidelines"),
            ("Medicine", "Medicines"),
            ("Clinical Skill", "Adult Patient Guidelines"),
        ),
    ),
)

_BY_ID = {s.id: s for s in REGISTRY}


def get_service(service_id: str) -> Service:
    return _BY_ID[service_id]


def all_service_ids() -> tuple[str, ...]:
    return tuple(s.id for s in REGISTRY)
