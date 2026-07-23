from rest_framework.routers import DefaultRouter

# API viewsets are registered here as the models come online.
router = DefaultRouter()

# from .api import PatientViewSet, AppointmentViewSet
# router.register("patients", PatientViewSet)
# router.register("appointments", AppointmentViewSet)

urlpatterns = router.urls
