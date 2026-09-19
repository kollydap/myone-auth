from fastapi import APIRouter

router = APIRouter()


@router.get(
    "",
    response_model=dict,
    summary="Health Check",
    description="Check the health of the API",
)
async def health_check():
    return {"status": "ok"}
