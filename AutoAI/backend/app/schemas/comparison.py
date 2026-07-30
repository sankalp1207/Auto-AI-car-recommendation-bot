from pydantic import BaseModel

class ComparisonRequest(BaseModel):
    car1_id: int | None = None
    car2_id: int | None = None
    model1: str | None = None
    model2: str | None = None
    car1: str | None = None
    car2: str | None = None