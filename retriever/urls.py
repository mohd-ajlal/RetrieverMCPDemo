from django.urls import path

from retriever import views

urlpatterns = [
    path("devices/", views.devices_view, name="devices"),
    path("orders/", views.orders_view, name="orders"),
]
