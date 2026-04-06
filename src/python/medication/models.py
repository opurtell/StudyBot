from pydantic import BaseModel


class MedicationDose(BaseModel):
    name: str
    indication: str
    contraindications: str
    adverse_effects: str
    precautions: str
    dose: str
    cmg_reference: str
    is_icp_only: bool = False
