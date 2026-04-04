from app.managers.connection_manager import ConnectionManager
from app.managers.lift_manager import LiftManager


cm = ConnectionManager()
lm = LiftManager(cm)