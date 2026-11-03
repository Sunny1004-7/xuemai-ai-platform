"""Business router composition; domains keep independent, testable boundaries."""
from fastapi import APIRouter
from . import routes_courses, routes_practice, routes_resources, routes_student, routes_teaching

router=APIRouter()
for module in (routes_courses, routes_practice, routes_resources, routes_student, routes_teaching):
    router.include_router(module.router)
