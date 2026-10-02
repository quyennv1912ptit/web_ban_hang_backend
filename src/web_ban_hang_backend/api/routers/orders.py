from fastapi import APIRouter

router = APIRouter(
    prefix="/orders",
    tags=["Orders"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def get_orders_history():
    pass
@router.get("/{id}")
async def get_order_info(id: str):
    pass

@router.post("/")
async def create_order():
    pass

@router.put("/{id}")
async def update_order_info(id: str):
    pass

@router.delete("/{id}")
async def cancel_order(id: str):
    pass