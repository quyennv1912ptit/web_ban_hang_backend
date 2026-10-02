from fastapi import APIRouter

router = APIRouter(
    prefix="/cart",
    tags=["Cart"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def get_all_products_in_cart():
    pass

@router.post("/")
async def add_products_to_cart():
    pass

@router.put("/{product_id}")
async def update_products_in_cart(product_id: str):
    pass

@router.delete("/{product_id}")
async def delete_products_from_cart(product_id: str):
    pass