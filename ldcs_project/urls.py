"""
URL configuration for ldcs_project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.views.generic.base import RedirectView
from django.conf.urls import handler400, handler403, handler404, handler500

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include('xrayapp.urls')),
    # Add favicon redirect
    path('favicon.ico', 
         RedirectView.as_view(url='/static/images/favicon.ico', permanent=True)),
]

# Custom error handlers
handler400 = 'xrayapp.views.handler400'  # Bad Request
handler403 = 'xrayapp.views.handler403'  # Forbidden
handler404 = 'xrayapp.views.handler404'  # Not Found
handler500 = 'xrayapp.views.handler500'  # Server Error

# Additional handlers (these won't be automatically used by Django but can be triggered in middleware)
# handler401 = 'xrayapp.views.handler401'  # Unauthorized
# handler408 = 'xrayapp.views.handler408'  # Request Timeout
# handler429 = 'xrayapp.views.handler429'  # Too Many Requests
# handler502 = 'xrayapp.views.handler502'  # Bad Gateway
# handler503 = 'xrayapp.views.handler503'  # Service Unavailable
# handler504 = 'xrayapp.views.handler504'  # Gateway Timeout
