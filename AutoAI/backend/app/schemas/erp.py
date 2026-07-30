from pydantic import BaseModel

class ERPLoginRequest(BaseModel):
    student_id: str
    password: str
