"""
URL configuration for API project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve

from rest_framework import routers
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.reverse import reverse

from API.django_api import views

router = routers.DefaultRouter()
router.register(r"users", views.UserViewSet)
router.register(r"groups", views.GroupViewSet)
router.register(r"fieldboundaries", views.FieldBoundaryViewSet)
router.register(r"traces", views.ABTraceViewSet)
router.register(r"syncpartners", views.SyncPartnerViewSet)

FRONTEND_DIR = settings.BASE_DIR / "API" / "_frontend_test"


@api_view(["GET"])
def api_root(request, format=None):
    return Response(
        {
            "---------------------------Django:---------------------------------------------": " ",
        
            "users": reverse("user-list", request=request, format=format),
            "groups": reverse("group-list", request=request, format=format),
            "admin": "https://api.farmspt.ai.edvsz.hs-osnabrueck.de/admin/",

            "---------------------------MQTT:---------------------------------------------": " ",
            "mqtt-dashboard (early access/under development)": reverse("mqtt_dashboard", request=request, format=format),
            "mqtt-get-messages":  reverse("mqtt_getMessages", request=request, format=format),
            "mqtt-post-message":  reverse("mqtt_message", request=request, format=format),

            "--------------------------FarmSPT-Data:----------------------------------------": " ",
            "fieldboundaries": reverse("fieldboundary-list", request=request, format=format),
            "traces": reverse("abtrace-list", request=request, format=format),
            "manufacturers": reverse("get_manufacturers", request=request, format=format),

            "---------------------------Keycloak-Authentication:----------------------------": " ",
            "login": reverse("token_login", request=request, format=format),
            "create_manufacturer_withRealm": reverse("keycloak_create_manufacturer", request=request, format=format),
            "create_farmers_keycloakToDjango": reverse("create_farmers_keycloakToDjango", request=request, format=format),
            "add_user_to_group": reverse("add_user_to_group", request=request, format=format),
            "define_sync_partner": reverse("define_sync_partners", request=request, format=format),

            "---------------------------Frontend:--------------------------------------------": " ",
            "Viewer:": "https://frontend.farmspt.ai.edvsz.hs-osnabrueck.de/",

            "---------------------------OIDC (Deprecated):-----------------------------------": " ",
            "oidc ###deprecated###": request.build_absolute_uri("/oidc/authenticate/"),
        }
    )


urlpatterns = [
    path("", api_root, name="api-root"),
    path("api-auth/", include("rest_framework.urls", namespace="rest_framework")),
    path("admin/", admin.site.urls),
    path("app/<path:path>", serve, {"document_root": FRONTEND_DIR}),
    path("app/", serve, {"path": "index.html", "document_root": FRONTEND_DIR}),
    path("api/login/", views.token_login, name="token_login"),
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("api/keycloak/manufacturers/", views.keycloak_create_manufacturer, name="keycloak_create_manufacturer"),
    path("api/keycloak/farmers/", views.create_farmers_keycloakToDjango, name="create_farmers_keycloakToDjango"),
    path("api/keycloak/add-user-to-group/", views.add_user_to_group, name="add_user_to_group"),
    path("api/mqtt-message/", views.mqtt_message, name="mqtt_message"),        
    path("api/mqtt-get-messages/", views.mqtt_getMessages, name="mqtt_getMessages"),  
    path("mqtt-dashboard/", views.DashboardView.as_view(), name='mqtt_dashboard'),  
    path("api/mqtt-latest-timestamp/", views.mqtt_latest_timestamp, name="mqtt_latest_timestamp"),
    path("api/mqtt-messages/", views.mqtt_delete_all_messages, name="mqtt_delete_all_messages"),
    path("api/mqtt-messages/<str:message_id>/", views.mqtt_delete_message, name="mqtt_delete_message"),
    path("api/get-manufacturers/", views.get_manufacturers, name="get_manufacturers"),
    path("api/define-sync-partners/", views.define_sync_partners, name="define_sync_partners"),

    path("", include(router.urls)),
    
]
