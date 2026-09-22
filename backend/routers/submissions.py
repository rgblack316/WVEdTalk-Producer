"""Dashboard record-keeping for public story submissions: list them, change status, send a
thank-you email, or delete. Mounted behind the auth guard in server.py."""

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException

from lib import email_digest
from lib.db import db
from models.submission import StorySubmission, SubmissionUpdate

router = APIRouter(tags=["submissions"])

_VALID = {"new", "used", "archived", "rejected"}


@router.get("/submissions", response_model=List[StorySubmission])
async def list_submissions():
    docs = await db.submissions.find({}, {"_id": 0}).sort("submitted_at", -1).to_list(1000)
    return [StorySubmission(**d) for d in docs]


@router.patch("/submissions/{sid}", response_model=StorySubmission)
async def update_submission(sid: str, body: SubmissionUpdate):
    updates: dict = {}
    if body.status is not None:
        if body.status not in _VALID:
            raise HTTPException(status_code=422, detail="Unknown status")
        updates["status"] = body.status
    if body.note is not None:
        updates["note"] = body.note[:2000]
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    res = await db.submissions.update_one({"id": sid}, {"$set": updates})
    if not res.matched_count:
        raise HTTPException(status_code=404, detail="Submission not found")
    doc = await db.submissions.find_one({"id": sid}, {"_id": 0})
    return StorySubmission(**doc)


@router.post("/submissions/{sid}/reject", response_model=StorySubmission)
async def reject_submission(sid: str):
    """Reject a not-WV-relevant tip and email the reader a short 'not a fit this time' note.
    The rejection still applies even if the email can't be sent."""
    doc = await db.submissions.find_one({"id": sid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")
    try:
        await email_digest.send_submission_rejection(
            name=doc.get("name", ""), email=doc.get("email", ""), url=doc.get("url", "")
        )
    except Exception:
        pass
    await db.submissions.update_one(
        {"id": sid}, {"$set": {"status": "rejected", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    doc["status"] = "rejected"
    return StorySubmission(**doc)


@router.post("/submissions/{sid}/thank", response_model=StorySubmission)
async def thank_submission(sid: str):
    doc = await db.submissions.find_one({"id": sid}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Submission not found")
    sent = await email_digest.send_submission_thanks(
        name=doc.get("name", ""), email=doc.get("email", ""), url=doc.get("url", "")
    )
    if not sent:
        raise HTTPException(status_code=502, detail="Could not send the thank-you email.")
    await db.submissions.update_one(
        {"id": sid}, {"$set": {"thanked": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    doc["thanked"] = True
    return StorySubmission(**doc)


@router.delete("/submissions/{sid}")
async def delete_submission(sid: str):
    await db.submissions.delete_one({"id": sid})
    return {"ok": True}
