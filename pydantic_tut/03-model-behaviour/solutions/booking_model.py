from pydantic import BaseModel, Field, computed_field


class Booking(BaseModel):
    
    user_id : int
    room_id : int
    nights : int = Field(
        ...,
        ge= 1
    )
    rate_per_night : float

    @computed_field
    @property
    def total_amount(self) -> float:
        total_amount = self.nights * self.rate_per_night
        return total_amount