from rest_framework.routers import DefaultRouter

<<<<<<< HEAD
from . import api

router = DefaultRouter()
router.register("patients", api.PatientViewSet)
router.register("appointments", api.AppointmentViewSet)
router.register("episodes", api.EpisodeViewSet)
router.register("followup-seen", api.FollowupSeenEpisodeViewSet)
router.register("encounters", api.EncounterViewSet)
router.register("staff", api.StaffViewSet)
router.register("roster", api.RosterViewSet)
=======
# API viewsets are registered here as the models come online.
router = DefaultRouter()

# from .api import PatientViewSet, AppointmentViewSet
# router.register("patients", PatientViewSet)
# router.register("appointments", AppointmentViewSet)
>>>>>>> origin/main

urlpatterns = router.urls
