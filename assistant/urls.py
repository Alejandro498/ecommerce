from django.urls import path
from . import views

urlpatterns = [
    path('', views.assistant, name='assistant'),
]
