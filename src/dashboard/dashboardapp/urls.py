from django.urls import path
from . import views

urlpatterns = [
    path('', views.render_dashboard, name='render_dashboard'),
    path('render/', views.render_dashboard, name='render_dashboard')
]