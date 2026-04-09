import chromadb
import pytest


@pytest.fixture
def seeded_chroma():
    client = chromadb.Client()

    for name in ["paramedic_notes", "cmg_guidelines"]:
        try:
            client.delete_collection(name)
        except Exception:
            pass

    notes = client.create_collection(
        "paramedic_notes", metadata={"hnsw:space": "cosine"}
    )
    notes.add(
        ids=["note_1", "note_2", "note_3", "note_4"],
        documents=[
            "Adrenaline 1mg IV every 3-5 minutes for cardiac arrest.",
            "Haemorrhage control with tourniquet for traumatic amputation.",
            "Pathophysiology of myocardial infarction and acute coronary syndromes.",
            "Clinical skills for neurological assessment including GCS and pupil checks.",
        ],
        metadatas=[
            {
                "source_type": "ref_doc",
                "source_file": "cardiac.md",
                "categories": "Cardiac",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
            {
                "source_type": "notability_note",
                "source_file": "trauma.note",
                "categories": "Trauma",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
            {
                "source_type": "notability_note",
                "source_file": "patho_mi.note",
                "categories": "Pathophysiology,Clinical Guidelines",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
            {
                "source_type": "notability_note",
                "source_file": "neuro_skills.note",
                "categories": "Clinical Skills,General Paramedicine",
                "chunk_index": 0,
                "last_modified": "2024-01-01",
                "has_review_flag": False,
            },
        ],
    )

    cmgs = client.create_collection("cmg_guidelines")
    cmgs.add(
        ids=["cmg_1", "cmg_2"],
        documents=[
            "CMG 14.1: Adult cardiac arrest. Defibrillation 200J biphasic. Adrenaline 1mg IV/IO after second shock.",
            "CMG 7: Spinal motion restriction. Apply cervical collar. Secure to spinal board.",
        ],
        metadatas=[
            {
                "source_type": "cmg",
                "source_file": "cmg_14.json",
                "cmg_number": "14",
                "section": "Cardiac",
                "chunk_type": "protocol",
                "last_modified": "2024-01-01",
                "is_icp_only": False,
                "visibility": "both",
            },
            {
                "source_type": "cmg",
                "source_file": "cmg_7.json",
                "cmg_number": "7",
                "section": "Trauma",
                "chunk_type": "protocol",
                "last_modified": "2024-01-01",
                "is_icp_only": False,
                "visibility": "both",
            },
        ],
    )

    cmgs.add(
        ids=["med_1"],
        documents=[
            "Adrenaline (epinephrine) 1:10 000. Indication: cardiac arrest. Dose: 1 mg IV/IO every 3-5 minutes.",
        ],
        metadatas=[
            {
                "source_type": "cmg",
                "source_file": "CMG_03_Adrenaline.json",
                "cmg_number": "03",
                "section": "Medicine",
                "chunk_type": "dosage",
                "last_modified": "2024-01-01",
                "is_icp_only": False,
                "visibility": "both",
            },
        ],
    )

    return client
