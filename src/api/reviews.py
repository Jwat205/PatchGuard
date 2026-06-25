from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import verify_jwt_token
from src.db.database import get_db
from src.models.postgres_models import Finding, PRReview
from src.models.schemas import APIResponse

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("", response_model=APIResponse)
async def list_reviews(
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(verify_jwt_token),
) -> APIResponse:
    result = await db.execute(select(PRReview).order_by(PRReview.created_at.desc()).limit(50))
    reviews = result.scalars().all()
    data = [
        {
            "id": r.id,
            "repo": r.repo_full_name,
            "pr_number": r.pr_number,
            "status": r.status,
            "latency_ms": r.latency_ms,
            "quality_findings": r.quality_findings,
            "security_findings": r.security_findings,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]
    return APIResponse(success=True, message="ok", data={"reviews": data})


@router.get("/{review_id}", response_model=APIResponse)
async def get_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(verify_jwt_token),
) -> APIResponse:
    result = await db.execute(select(PRReview).where(PRReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")

    findings_result = await db.execute(select(Finding).where(Finding.review_id == review_id))
    findings = findings_result.scalars().all()

    return APIResponse(
        success=True,
        message="ok",
        data={
            "review": {
                "id": review.id,
                "repo": review.repo_full_name,
                "pr_number": review.pr_number,
                "status": review.status,
                "summary": review.summary,
                "latency_ms": review.latency_ms,
                "agent_results": review.agent_results,
                "created_at": review.created_at.isoformat() if review.created_at else None,
            },
            "findings": [
                {
                    "id": f.id,
                    "agent_type": f.agent_type,
                    "file_path": f.file_path,
                    "line_number": f.line_number,
                    "finding_type": f.finding_type,
                    "severity": f.severity,
                    "message": f.message,
                    "is_blocking": f.is_blocking,
                }
                for f in findings
            ],
        },
    )
