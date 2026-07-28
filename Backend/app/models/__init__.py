from app.models.base import Base
from app.models.user import User
from app.models.session import Session, EmailVerification
from app.models.estimation import EstimationSession, DraftEstimationSession, InPlatformNotification

# This ensures all models are imported and registered with Base.metadata
