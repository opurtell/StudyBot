"""Static clinical dictionary and category mappings.

Maps Notability subject folder names to canonical clinical categories,
and provides domain-specific term lists for OCR cleaning context.
"""

CANONICAL_CATEGORIES = [
    "Clinical Guidelines",
    "Medication Guidelines",
    "Operational Guidelines",
    "Clinical Skills",
    "Pathophysiology",
    "Pharmacology",
    "ECGs",
    "General Paramedicine",
]

SUBJECT_TO_CATEGORY: dict[str, str] = {
    "ACTAS": "Clinical Guidelines",
    "CAA Medical emergencies 1": "Clinical Guidelines",
    "CNA308 Legal and Ethical": "Operational Guidelines",
    "CSA236 Pharmacology": "Pharmacology",
    "General Paramedicine": "General Paramedicine",
    "CAA107 Principles of Paramedic Practice": "Clinical Skills",
    "CAA209 Evidence Based Research Methods": "General Paramedicine",
    "CAA210 Mental Health Care in Out of Hospital Practice": "Clinical Guidelines",
    "CNA151 Health and Health Care in Australia": "General Paramedicine",
    "Orientation": "General Paramedicine",
    "CAA108 paramedic practice 2": "Clinical Skills",
    "CNA146 Aging": "General Paramedicine",
    "CNA156 Aboriginal": "General Paramedicine",
    "CNA157 Diversity": "General Paramedicine",
    "CXA107 intro to bioscience": "Pathophysiology",
    "CAA109 placement": "Clinical Skills",
    "CAA205 Med Emergencies": "Clinical Guidelines",
    "CNA308 Ethics and Law": "Operational Guidelines",
    "Arts and Dementia": "General Paramedicine",
    "CAA206 Med Emerg 2": "Clinical Guidelines",
    "CXA206 Bio 1": "Pathophysiology",
    "CAA306 Trauma": "Clinical Guidelines",
    "CXA309 Health Services": "General Paramedicine",
    "CXA310 Bio 2": "Pathophysiology",
    "CAA305 Environmental Emrgencies": "Clinical Guidelines",
    "CAA307 Obstetrics and Paediatrics": "Clinical Guidelines",
    "CAA309 Professional development": "Operational Guidelines",
}

DEFAULT_CATEGORY = "General Paramedicine"

CLINICAL_TERMS: dict[str, list[str]] = {
    "Pharmacology": [
        "adrenaline",
        "amiodarone",
        "midazolam",
        "ondansetron",
        "fentanyl",
        "morphine",
        "paracetamol",
        "ibuprofen",
        "salbutamol",
        "ipratropium",
        "ketamine",
        "methoxyflurane",
        "tranexamic acid",
        "naloxone",
        "atropine",
        "glucagon",
        "dexamethasone",
        "hydrocortisone",
        "diazepam",
        "lorazepam",
        "metoclopramide",
        "glyceryl trinitrate",
        "aspirin",
        "enoxaparin",
        "clopidogrel",
        "tenecteplase",
        "heparin",
        "noradrenaline",
    ],
    "Clinical Guidelines": [
        "anaphylaxis",
        "cardiac arrest",
        "acute coronary syndrome",
        "stroke",
        "seizure",
        "sepsis",
        "asthma",
        "COPD",
        "pneumothorax",
        "pulmonary oedema",
        "hypoglycaemia",
        "hyperglycaemia",
        "supraventricular tachycardia",
        "ventricular tachycardia",
        "ventricular fibrillation",
        "bradycardia",
        "hypertension",
    ],
    "Clinical Skills": [
        "laryngoscopy",
        "intubation",
        "cannulation",
        "tourniquet",
        "defibrillation",
        "cardioversion",
        "chest decompression",
        "cricothyroidotomy",
        "splinting",
        "traction",
        "suction",
        "bag-valve-mask",
        "oropharyngeal airway",
        "nasopharyngeal airway",
        "supraglottic airway",
        "i-gel",
        "intraosseous",
    ],
    "Pathophysiology": [
        "haemorrhage",
        "hypovolaemia",
        "perfusion",
        "ventilation",
        "oxygenation",
        "haemoglobin",
        "erythrocyte",
        "leukocyte",
        "myocardium",
        "cerebral",
        "renal",
        "hepatic",
        "ischaemia",
        "infarction",
        "oedema",
        "inflammation",
        "coagulation",
    ],
    "ECGs": [
        "sinus rhythm",
        "atrial fibrillation",
        "atrial flutter",
        "ST elevation",
        "ST depression",
        "T wave inversion",
        "bundle branch block",
        "QRS complex",
        "PR interval",
        "QT interval",
        "P wave",
        "axis deviation",
    ],
    "Operational Guidelines": [
        "triage",
        "clinical handover",
        "ISBAR",
        "documentation",
        "scope of practice",
        "duty of care",
        "consent",
        "capacity",
        "mandatory reporting",
        "clinical governance",
    ],
    "Medication Guidelines": [
        "indication",
        "contraindication",
        "dose",
        "route",
        "adverse effect",
        "interaction",
        "pharmacokinetics",
        "pharmacodynamics",
        "therapeutic index",
        "half-life",
    ],
}


def get_category(folder_name: str) -> str:
    """Return the canonical category for a Notability folder name."""
    return SUBJECT_TO_CATEGORY.get(folder_name.strip(), DEFAULT_CATEGORY)


def get_terms_for_category(category: str) -> list[str]:
    """Return clinical terms list for a category, or empty list if unknown."""
    return CLINICAL_TERMS.get(category, [])


FILE_TO_CATEGORIES: dict[str, list[str]] = {
    "REFdocs/Reference Info ACTAS CMGs.md": [
        "Medication Guidelines",
        "Clinical Guidelines",
    ],
    "REFdocs/ACTAS Policies and procedures.md": ["Operational Guidelines"],
    "CPDdocs/ECGs.md": ["ECGs", "Clinical Skills"],
    "CPDdocs/CAA306 AT1 Part 3.md": ["Clinical Guidelines"],
    "CPDdocs/CAA306 AT1 Topic 2.md": [
        "Clinical Guidelines",
        "Clinical Skills",
    ],
    "CPDdocs/CAA306 AT1 Part 4.md": ["Clinical Guidelines"],
    "CPDdocs/Professional development.md": ["Clinical Guidelines", "Pathophysiology"],
    "CPDdocs/Febrile seizures.md": ["Clinical Guidelines", "Pathophysiology"],
    "CPDdocs/Miscarriage.md": ["Clinical Guidelines", "Pathophysiology"],
    "CPDdocs/Neurological Assessment.md": ["Clinical Skills"],
    "CPDdocs/Finals Study.md": ["General Paramedicine"],
}

DIR_TO_SOURCE_TYPE: dict[str, str] = {
    "REFdocs": "ref_doc",
    "CPDdocs": "cpd_doc",
}


def get_categories_for_file(relative_path: str) -> list[str]:
    return FILE_TO_CATEGORIES.get(relative_path, [DEFAULT_CATEGORY])


def get_source_type_for_dir(dir_name: str) -> str:
    if dir_name not in DIR_TO_SOURCE_TYPE:
        raise ValueError(f"Unknown source directory: {dir_name!r}")
    return DIR_TO_SOURCE_TYPE[dir_name]
