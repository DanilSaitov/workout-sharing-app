from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('message/', views.message, name='message'),
    path('calendar/', views.calendar_view, name='calendar'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('settings/', views.settings, name='settings'),
    path('login/', views.loginPage, name='login'),
    path('logout/', views.logoutUser, name='logout'),
    path('register/', views.registerPage, name='register'),
    
    # Workout Request CRUD
    path('workout/create/', views.create_workout_request, name='create_workout_request'),
    path('workout/edit/<int:workout_id>/', views.edit_workout_request, name='edit_workout_request'),
    path('workout/delete/<int:workout_id>/', views.delete_workout_request, name='delete_workout_request'),
    path('workout/cancel/<int:invitation_id>/', views.cancel_workout, name='cancel_workout'),
    path('workout-request/delete/<int:workout_id>/', views.cancel_workout_request, name='cancel_workout_request'),
    
    # Friend System
    path('friend/send/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('friend/accept/<str:username>/', views.accept_friend_request, name='accept_friend_request'),
    path('friend/reject/<str:username>/', views.reject_friend_request, name='reject_friend_request'),
    path('friends/', views.friend_list, name='friend_list'),
    path('friend/remove/<str:username>/', views.unfriend, name='unfriend'),
    
    # Messaging
    path('inbox/', views.inbox, name='inbox'),
    path('inbox/<str:username>/', views.conversation, name='conversation'),
    path('inbox/invitation/<int:invitation_id>/<str:action>/', views.respond_workout_invitation, name='respond_workout_invitation'),
    path('inbox/invitation/cancel/<int:invitation_id>/', views.cancel_workout_invitation, name='cancel_workout_invitation'),
    
    # Calendar API
    path('api/workouts/', views.workout_events_api, name='workout_events_api'),
    path('api/workouts/upcoming/', views.upcoming_workouts_api, name='upcoming_workouts_api'),
]
