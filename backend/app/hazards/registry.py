from app.hazards.base import Hazard
from app.hazards.heatwave import Heatwave

# Adding a hazard = write one class + add one entry here.
HAZARDS: dict[str, Hazard] = {
    "heatwave": Heatwave(),
}
