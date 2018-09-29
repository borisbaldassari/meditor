"""django_prosoul URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.11/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from django.contrib.auth import views as auth_views
from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import RedirectView

from prosoul.models import QualityModel

#############
# REST routes support
# Serializers define the API representation.

from rest_framework import routers, serializers, viewsets


class QualityModelSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = QualityModel
        fields = ('id', 'name', 'active', 'description', 'created_at', 'updated_at')
        # fields = ('id', 'name', 'active', 'description', 'created_by', 'created_at', 'updated_at')


# ViewSets define the view behavior.
class QualityModelViewSet(viewsets.ModelViewSet):
    queryset = QualityModel.objects.all()
    serializer_class = QualityModelSerializer


# Routers provide an easy way of automatically determining the URL conf.
router = routers.DefaultRouter()
router.register(r'qualitymodels', QualityModelViewSet)
#############


urlpatterns = [
    url(r'^$', RedirectView.as_view(url='/prosoul')),
    url(r'^admin/', admin.site.urls, name="admin"),
    url(r'^accounts/login/$', auth_views.LoginView.as_view()),
    url('^', include('django.contrib.auth.urls')),
    url('^', include(router.urls)),
    url(r'^prosoul/', include('prosoul.urls', namespace='prosoul')),
    url(r'^api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]
