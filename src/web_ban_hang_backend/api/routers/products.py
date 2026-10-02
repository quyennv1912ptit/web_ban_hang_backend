from fastapi import APIRouter

router = APIRouter(
    prefix="/products",
    tags=["Products"],
    responses={404: {"description": "Not found"}},
)

@router.get("/")
async def get_all_products():
    pass

@router.get("/{id}")
async def get_product_detail(id: str):
    pass

@router.get("/{id}/reviews")
async def get_product_reviews(id: str):
    pass

@router.post("/{id}/reviews")
async def add_product_reviews(id: str):
    pass

@router.put("/{id}/reviews")
async def update_product_reviews(id: str):
    pass

@router.delete("/{id}/reviews")
async def delete_product_reviews(id: str):
    pass