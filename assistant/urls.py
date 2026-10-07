from django.urls import path

from . import views


urlpatterns = [
    path('', views.assistant, name='assistant'),
    path('chat/', views.assistant_chat, name='assistant_chat'),
]