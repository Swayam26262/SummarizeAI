from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from .views import MyTokenObtainPairView, MyTokenRefreshView, user_login, user_logout

urlpatterns = [
    path('', views.index, name='index.html'),
    path('login', views.user_login, name='login'),
    path('signup', views.user_signup, name='signup'),
    path('logout', views.user_logout, name='logout'),
    path('generate-summary', views.generate_summary, name='generate-summary'),
    path('all-summaries', views.all_summaries, name='all-summaries'),
    path('progress', views.progress, name='progress'),
    path('video-summaries/', views.video_summaries, name='video-summaries'),
    path('video-summaries/summary-details/<int:pk>/', views.summary_details, name='summary-details'),
    path('contact', views.contact, name='contact'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),
    path('api/token/', MyTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', MyTokenRefreshView.as_view(), name='token_refresh'),
    path('login/', user_login, name='user_login'),
    path('logout/', user_logout, name='user_logout'),
]
