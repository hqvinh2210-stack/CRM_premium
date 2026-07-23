from fastapi import APIRouter

from pos.routers import (
    ai_pos,
    auth,
    catalog,
    customers,
    events,
    integrations,
    inventory,
    loyalty,
    orders,
    payments,
    promotions,
    reports,
    tasks,
)

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router, tags=["auth"])
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(customers.router, tags=["customers"])
api_router.include_router(orders.router, tags=["orders"])
api_router.include_router(reports.router, tags=["reports"])
api_router.include_router(loyalty.router)
api_router.include_router(inventory.router)
api_router.include_router(promotions.router)
api_router.include_router(ai_pos.router)
api_router.include_router(payments.router)
api_router.include_router(events.router)
api_router.include_router(tasks.router)
api_router.include_router(integrations.router)
