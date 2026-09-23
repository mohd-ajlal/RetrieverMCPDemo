from django.urls import path

from organizations import views

urlpatterns = [
    path("organization/", views.organization_view, name="organization"),
    path("organization/switch/", views.switch_organization, name="switch_organization"),
]
