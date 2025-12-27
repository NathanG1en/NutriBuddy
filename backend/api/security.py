import firebase_admin
from firebase_admin import auth, firestore
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global variable to track initialization status
_firebase_initialized = False
_db_client = None


def init_firebase():
    global _firebase_initialized, _db_client
    try:
        firebase_admin.get_app()
        _firebase_initialized = True
        _db_client = firestore.client()
    except ValueError:
        try:
            # Try to get project ID from env
            project_id = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv(
                "VITE_FIREBASE_PROJECT_ID"
            )

            options = {}
            if project_id:
                options["projectId"] = project_id

            # Requires GOOGLE_APPLICATION_CREDENTIALS for full access,
            # but for public auth verification, options might be enough if using default creds.
            # However, verify_id_token() specifically asks for a project ID usually.

            cred = None
            # If explicit credentials path is provided
            if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
                from firebase_admin import credentials

                cred = credentials.Certificate(
                    os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                )

            firebase_admin.initialize_app(cred, options)
            _firebase_initialized = True
            _db_client = firestore.client()
            logger.info(
                f"Firebase Admin initialized successfully (Project: {project_id})"
            )
        except Exception as e:
            logger.warning(f"Firebase Admin could not be initialized: {e}")
            _firebase_initialized = False


# Initialize on module load or call explicitly in main.py
init_firebase()

security = HTTPBearer()


def get_db():
    if not _db_client:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return _db_client


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)):
    """
    Verifies the Firebase ID token and returns the decoded user data.
    """
    if not _firebase_initialized:
        # Fallback for development/testing if credentials aren't set up yet
        # WARNING: This allows access without valid auth in dev mode if init failed.
        # Ideally, we should raise an error, but for smooth integration, we might want to just log it.
        # For security, let's raise error but with specific message.
        logger.warning("Firebase not initialized, rejecting request.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service not configured",
        )

    token = creds.credentials
    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception as e:
        logger.error(f"Error verifying token: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
