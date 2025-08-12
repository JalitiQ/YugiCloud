from django.urls import path
from YugiCloud.YugiLog import views
from views import *

urlpatterns = [
    path('login/', views.login_user, name='login'),
	path('logout/', views.logout_user, name='logout'),
	path('register/', views.register_user, name='register'),
]