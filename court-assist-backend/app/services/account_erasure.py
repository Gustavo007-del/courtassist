"""Authenticated erasure request and operator-reviewed purge."""

import argparse
import shutil
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import delete, select, update

from app.core.config import get_settings
from app.core.security import verify_password
from app.database.session import SessionLocal
from app.models.account_erasure import AccountErasure
from app.models.finance import AgreementHistory
from app.models.image_upload import ImageUpload
from app.models.notifications import NotificationDelivery, NotificationDeliveryAttempt, UserDevice
from app.models.research import ResearchAudit, ResearchImportBatch, ResearchNote, ResearchSourceMetadata
from app.models.user import PasswordResetToken, RefreshSession, User
from app.services import document_storage, image_service
from app.services.auth_service import lock_account, now_utc
from app.services.notification_devices import revoke


def request_erasure(db, user_id, password):
    user = lock_account(db, user_id)
    if not user or not user.is_active or not verify_password(password, user.password_hash):
        raise HTTPException(400, "Account verification failed")
    now = now_utc()
    receipt = AccountErasure(id=uuid4(), user_id=user.id, requested_at=now)
    user.is_active = False
    db.add(receipt)
    db.execute(update(RefreshSession).where(RefreshSession.user_id == user.id,
        RefreshSession.revoked_at.is_(None)).values(revoked_at=now))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == user.id))
    for device in db.scalars(select(UserDevice).where(UserDevice.user_id == user.id, UserDevice.revoked_at.is_(None))):
        revoke(db, device)
    db.commit()
    return receipt


def remove_private_files(db, owner):
    settings = get_settings()
    if settings.document_s3_bucket:
        s3 = document_storage.client()
        bucket = settings.document_s3_bucket
        for stage in ("staging", "stored"):
            prefix = f"documents/{stage}/{owner}/"
            while True:
                page = s3.list_object_versions(Bucket=bucket, Prefix=prefix, MaxKeys=1000)
                objects = [{"Key": item["Key"], "VersionId": item["VersionId"]}
                    for field in ("Versions", "DeleteMarkers") for item in page.get(field, [])]
                if not objects:
                    break
                if any(not item["Key"].startswith(prefix) for item in objects):
                    raise RuntimeError("Unexpected object prefix")
                result = s3.delete_objects(Bucket=bucket, Delete={"Objects": objects, "Quiet": True})
                if result.get("Errors"):
                    raise RuntimeError("Private object deletion failed")
    storage = image_service.PrivateImageStorage()
    folder = storage.root / str(owner)
    if folder.exists():
        shutil.rmtree(folder)
    for upload_id in db.scalars(select(ImageUpload.id).where(ImageUpload.user_id == owner)):
        temporary = storage.temporary(upload_id)
        temporary.unlink(missing_ok=True)
        temporary.with_suffix(".clean").unlink(missing_ok=True)


def purge(db, receipt_id):
    receipt = db.get(AccountErasure, receipt_id, with_for_update=True)
    if receipt is None:
        raise ValueError("Unknown erasure receipt")
    if receipt.completed_at:
        return
    owner = receipt.user_id
    user = lock_account(db, owner)
    if user is None or user.is_active:
        raise ValueError("Account must have a recorded request and disabled access")
    remove_private_files(db, owner)
    # Delete dependents whose foreign keys restrict user-level cascades.
    for model in (NotificationDeliveryAttempt, NotificationDelivery, ResearchAudit, ResearchSourceMetadata,
                  ResearchImportBatch, ResearchNote, AgreementHistory):
        db.execute(delete(model).where(model.user_id == owner))
    db.execute(delete(User).where(User.id == owner))
    receipt.user_id = None
    receipt.completed_at = now_utc()
    db.commit()


def main():
    parser = argparse.ArgumentParser(description="Purge one approved account erasure request")
    parser.add_argument("receipt_id", type=UUID)
    parser.add_argument("--confirm-erasure", action="store_true", required=True)
    args = parser.parse_args()
    try:
        with SessionLocal() as db:
            purge(db, args.receipt_id)
    except Exception:
        parser.exit(1, "Erasure incomplete. Check storage permissions, retention locks and database integrity before retrying.\n")
    print("Erasure completed")


if __name__ == "__main__":
    main()

