from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("start/", views.start, name="start"),
    path("check-nickname/", views.check_nickname, name="check_nickname"),
    path("logout/", views.logout, name="logout"),
]
