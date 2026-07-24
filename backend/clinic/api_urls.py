from rest_framework.routers import DefaultRouter

from . import api

router = DefaultRouter()
router.register("patients", api.PatientViewSet)
router.register("appointments", api.AppointmentViewSet)
router.register("episodes", api.EpisodeViewSet)
router.register("followup-seen", api.FollowupSeenEpisodeViewSet)
router.register("encounters", api.EncounterViewSet)
router.register("staff", api.StaffViewSet)
router.register("roster", api.RosterViewSet)

urlpatterns = router.urls
