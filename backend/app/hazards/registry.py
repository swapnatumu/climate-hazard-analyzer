from app.hazards.base import Hazard
from app.hazards.drought import Drought
from app.hazards.heatwave import Heatwave
from app.hazards.rainfall import HeavyRainfall

# Adding a hazard = write one class + add one entry here.
HAZARDS: dict[str, Hazard] = {
    "heatwave": Heatwave(),
    "drought": Drought(),
    "rainfall": HeavyRainfall(),
}
