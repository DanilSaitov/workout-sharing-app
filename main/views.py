from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.db.models import Q, Count, F
from .models import User, WorkoutRequest, FriendRequest, Friendship, Message, WorkoutInvitation
from .forms import WorkoutRequestForm
from django.utils import timezone
from datetime import datetime, timedelta
from django.db import transaction
from django.views.decorators.http import require_http_methods

# Create your views here.
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email', 'username', 'profile_picture', 'password1', 'password2']

def index(request):
    # Initial filter settings
    filter_conditions = {
        'date__gte': timezone.now().date(),
        'is_past': False,
        'is_full': False
    }
    
    # Apply filters based on GET parameters
    if 'body_part' in request.GET and request.GET['body_part'] and request.GET['body_part'] != 'All':
        # Use case-insensitive contains search for body part
        filter_conditions['body_part__icontains'] = request.GET['body_part']
    
    if 'experience_level' in request.GET and request.GET['experience_level'] and request.GET['experience_level'] != 'All':
        # Use case-insensitive contains search for experience level
        filter_conditions['experience_level__icontains'] = request.GET['experience_level']
    
    if 'date' in request.GET and request.GET['date']:
        try:
            selected_date = datetime.strptime(request.GET['date'], '%Y-%m-%d').date()
            # Override the default date filter
            filter_conditions.pop('date__gte', None)
            filter_conditions['date'] = selected_date
        except ValueError:
            # If date format is invalid, fall back to default filter
            pass
    
    if 'search' in request.GET and request.GET['search']:
        search_query = request.GET['search']
        # Keep the basic filters but add Q objects for searching
        basic_filters = filter_conditions.copy()
        filter_conditions = {}
        workout_requests = WorkoutRequest.objects.filter(
            Q(**basic_filters) & 
            (Q(body_part__icontains=search_query) | 
             Q(experience_level__icontains=search_query) |
             Q(description__icontains=search_query) |
             Q(user__username__icontains=search_query))
        ).order_by('date', 'time')
    else:
        # Normal filtering without search
        workout_requests = WorkoutRequest.objects.filter(**filter_conditions).order_by('date', 'time')
    
    if request.user.is_authenticated:
        created_workouts = WorkoutRequest.objects.filter(user=request.user).count()
        participated_workouts = WorkoutInvitation.objects.filter(receiver=request.user, status__in=['accepted', 'completed']).count()
        total_workouts = created_workouts + participated_workouts
        completed_workouts = WorkoutInvitation.objects.filter(receiver=request.user, status='completed').count()
        completed_workouts += WorkoutRequest.objects.filter(user=request.user, is_past=True).count()
        
        # Get recent messages
        recent_messages = Message.objects.filter(receiver=request.user).order_by('-created_at')[:5]
        
        # Get recent workout invitations
        recent_invitations = WorkoutInvitation.objects.filter(receiver=request.user).order_by('-created_at')[:5]
        
        # Get pending friend requests
        friend_requests = FriendRequest.objects.filter(to_user=request.user)
        
        # Calculate favorite body part based on workout history
        body_part_count = {}
        user_workouts = WorkoutRequest.objects.filter(user=request.user)
        user_invitations = WorkoutInvitation.objects.filter(receiver=request.user, status__in=['accepted', 'completed'])
        
        for workout in user_workouts:
            body_part = workout.body_part
            if body_part in body_part_count:
                body_part_count[body_part] += 1
            else:
                body_part_count[body_part] = 1
                
        for invite in user_invitations:
            body_part = invite.workout_request.body_part
            if body_part in body_part_count:
                body_part_count[body_part] += 1
            else:
                body_part_count[body_part] = 1
        
        favorite_body_part = None
        if body_part_count:
            favorite_body_part = max(body_part_count.items(), key=lambda x: x[1])
        
        context = {
            'workout_requests': workout_requests,
            'total_workouts': total_workouts,
            'created_workouts': created_workouts,
            'completed_workouts': completed_workouts,
            'favorite_body_part': favorite_body_part,
            'recent_messages': recent_messages,
            'recent_invitations': recent_invitations,
            'friend_requests': friend_requests,
        }
    else:
        context = {
            'workout_requests': workout_requests,
        }
    return render(request, 'index.html', context)

def message(request):
    return render(request, 'message.html')

def calendar_view(request):
    """
    Main calendar view
    """
    return render(request, 'calendar.html')

def profile(request, username):
    profile_user = get_object_or_404(User, username=username)
    is_friend = False
    friend_request_sent = False
    friend_request_received = False
    
    # Handle bio update form submission
    if request.method == 'POST' and request.user.is_authenticated and request.user == profile_user:
        if 'bio' in request.POST:
            profile_user.bio = request.POST.get('bio')
            profile_user.save()
            messages.success(request, "Bio updated successfully!")
            return redirect('profile', username=username)
    
    if request.user.is_authenticated:
        # Check if the users are friends
        is_friend = Friendship.objects.filter(
            Q(user1=request.user, user2=profile_user) | Q(user1=profile_user, user2=request.user)
        ).exists()
        
        # Check if the current user has sent a friend request to this user
        friend_request_sent = FriendRequest.objects.filter(
            from_user=request.user, to_user=profile_user
        ).exists()
        
        # Check if the current user has received a friend request from this user
        friend_request_received = FriendRequest.objects.filter(
            from_user=profile_user, to_user=request.user
        ).exists()
    
    # Get friends for the profile_user
    friends = []
    friendships = Friendship.objects.filter(
        Q(user1=profile_user) | Q(user2=profile_user)
    )
    
    for friendship in friendships:
        if friendship.user1 == profile_user:
            friends.append(friendship.user2)
        else:
            friends.append(friendship.user1)
    
    context = {
        'profile_user': profile_user,
        'is_friend': is_friend,
        'friend_request_sent': friend_request_sent,
        'friend_request_received': friend_request_received,
        'friends': friends,
    }
    return render(request, 'profile.html', context)

@login_required(login_url='login')
def settings(request):
    if request.method == 'POST':
        if 'email' in request.POST:
            request.user.email = request.POST.get('email')
            request.user.save()
            messages.success(request, "Email updated successfully!")
            return redirect('settings')
        elif 'username' in request.POST:
            request.user.username = request.POST.get('username')
            request.user.save()
            messages.success(request, "Username updated successfully!")
            return redirect('settings')
        elif 'password' in request.POST:
            form = PasswordChangeForm(request.user, request.POST)
            if form.is_valid():
                user = form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password updated successfully!")
                return redirect('settings')
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    return render(request, 'settings.html')

@login_required(login_url='login')
def workout_stats(request):
    """
    View for displaying workout statistics
    """
    # Get completed workouts
    created_workouts = WorkoutRequest.objects.filter(
        user=request.user
    ).order_by('-date')
    
    participated_workouts = WorkoutInvitation.objects.filter(
        receiver=request.user, 
        status__in=['accepted', 'completed', 'cancelled']
    ).select_related('workout_request').order_by('-created_at')
    
    # Calculate stats
    total_workouts = created_workouts.count() + participated_workouts.count()
    completed_created = created_workouts.filter(is_past=True).count()
    completed_participated = participated_workouts.filter(status='completed').count()
    total_completed = completed_created + completed_participated
    
    cancelled_created = WorkoutRequest.objects.filter(
        user=request.user, 
        workout_invitations__status='cancelled'
    ).distinct().count()
    
    cancelled_participated = participated_workouts.filter(status='cancelled').count()
    total_cancelled = cancelled_created + cancelled_participated
    
    # Calculate body part stats
    body_parts_data = {}
    
    # From created workouts
    for part in created_workouts.values('body_part').annotate(count=Count('body_part')):
        body_parts_data[part['body_part']] = part['count']
    
    # From participated workouts
    for part in participated_workouts.values('workout_request__body_part').annotate(count=Count('workout_request__body_part')):
        part_name = part['workout_request__body_part']
        if part_name:
            body_parts_data[part_name] = body_parts_data.get(part_name, 0) + part['count']
    
    body_parts = [{"name": k, "count": v} for k, v in body_parts_data.items()]
    body_parts.sort(key=lambda x: x['count'], reverse=True)
    
    context = {
        'total_workouts': total_workouts,
        'total_completed': total_completed,
        'total_cancelled': total_cancelled,
        'body_parts': body_parts,
        'created_workouts': created_workouts[:10],  # Show the last 10 workouts
        'participated_workouts': participated_workouts[:10],  # Show the last 10 workouts
    }
    
    return render(request, 'stats.html', context)

@login_required(login_url='login')
def activity_feed(request):
    """
    View for displaying recent activities
    """
    # Get recent activities (messages, workout cancellations, etc.)
    messages = Message.objects.filter(
        receiver=request.user
    ).order_by('-created_at')[:20]
    
    # Get workout invitations
    invitations = WorkoutInvitation.objects.filter(
        receiver=request.user
    ).select_related('workout_request', 'sender').order_by('-created_at')[:20]
    
    # Get friend requests
    friend_requests = FriendRequest.objects.filter(
        to_user=request.user
    ).select_related('from_user').order_by('-created_at')[:10]
    
    context = {
        'messages': messages,
        'invitations': invitations,
        'friend_requests': friend_requests,
    }
    
    return render(request, 'activity.html', context)

def loginPage(request):
    page = 'login'

    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        email = request.POST.get('email', '').lower()
        password = request.POST.get('password', '')

        # Add print statements for debugging
        print(f"Login attempt with email: {email}")
        
        try:
            # First check if a user with this email exists
            user_exists = User.objects.filter(email=email).exists()
            if not user_exists:
                messages.error(request, 'No user with that email exists')
                return render(request, 'login_register.html', {'page': page})
            
            # Try to authenticate
            user = authenticate(request, username=email, password=password)
            print(f"Authentication result: {user}")
            
            if user is not None:
                login(request, user)
                return redirect('index')
            else:
                messages.error(request, 'Invalid password')
                return render(request, 'login_register.html', {'page': page})
                
        except Exception as e:
            print(f"Login error: {str(e)}")
            messages.error(request, f'Login error: {str(e)}')
            return render(request, 'login_register.html', {'page': page})

    return render(request, 'login_register.html', {'page': page})

def logoutUser(request):
    logout(request)
    return redirect('index')

def registerPage(request):
    if request.user.is_authenticated:
        return redirect('index')

    form = CustomUserCreationForm()

    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.email = user.email.lower()
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
            user.save()
            
            # Authenticate the user with the EmailBackend
            authenticated_user = authenticate(
                request, 
                username=user.email, 
                password=form.cleaned_data['password1']
            )
            
            if authenticated_user is not None:
                login(request, authenticated_user)
                return redirect('index')
            else:
                messages.error(request, 'User created but unable to log in automatically. Please log in.')
                return redirect('login')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    return render(request, 'login_register.html', {'form': form})

# CRUD operations for WorkoutRequest model
@login_required(login_url='login')
@transaction.atomic
@require_http_methods(["GET", "POST"])
def create_workout_request(request):
    if request.method == 'POST':
        form = WorkoutRequestForm(request.POST)
        if form.is_valid():
            workout = form.save(commit=False)
            workout.user = request.user
            workout.save()  # This will trigger the save method in the model
            return redirect('index')
    else:
        form = WorkoutRequestForm()
    return render(request, 'workout_request_form.html', {'form': form})

@login_required(login_url='login')
def edit_workout_request(request, workout_id):
    workout_request = get_object_or_404(WorkoutRequest, id=workout_id)
    
    # Check if the user is the owner of the workout request
    if request.user != workout_request.user:
        messages.error(request, "You can only edit your own workout requests.")
        return redirect('index')
    
    if request.method == 'POST':
        form = WorkoutRequestForm(request.POST, instance=workout_request)
        if form.is_valid():
            form.save()
            messages.success(request, "Workout request updated successfully.")
            return redirect('index')
    else:
        form = WorkoutRequestForm(instance=workout_request)
    
    return render(request, 'workout_request_form.html', {'form': form, 'editing': True})

@login_required(login_url='login')
def delete_workout_request(request, workout_id):
    workout_request = get_object_or_404(WorkoutRequest, id=workout_id)
    
    # Check if the user is the owner of the workout request
    if request.user != workout_request.user:
        messages.error(request, "You can only delete your own workout requests.")
        return redirect('index')
    
    if request.method == 'POST':
        workout_request.delete()
        messages.success(request, "Workout request deleted successfully.")
        return redirect('index')
    
    return render(request, 'confirm_delete.html', {'workout_request': workout_request})

def list_workout_requests(request):
    workout_requests = WorkoutRequest.objects.all().order_by('-created_at')
    return render(request, 'index.html', {'workout_requests': workout_requests})

# Friend System Views
@login_required(login_url='login')
def send_friend_request(request, username):
    to_user = get_object_or_404(User, username=username)
    
    # Prevent sending friend request to yourself
    if request.user == to_user:
        messages.error(request, "You cannot send a friend request to yourself.")
        return redirect('profile', username=username)
    
    # Check if a friendship already exists
    friendship_exists = Friendship.objects.filter(
        Q(user1=request.user, user2=to_user) | Q(user1=to_user, user2=request.user)
    ).exists()
    
    if friendship_exists:
        messages.info(request, f"You are already friends with {username}.")
        return redirect('profile', username=username)
    
    # Check if there's a pending request
    request_exists = FriendRequest.objects.filter(from_user=request.user, to_user=to_user).exists()
    
    if request_exists:
        messages.info(request, f"You already sent a friend request to {username}.")
        return redirect('profile', username=username)
    
    # Check if there's a request from the other user
    reverse_request = FriendRequest.objects.filter(from_user=to_user, to_user=request.user).first()
    
    if reverse_request:
        # Automatically accept the reverse request
        friendship = Friendship(user1=request.user, user2=to_user)
        friendship.save()
        reverse_request.delete()
        messages.success(request, f"You are now friends with {username}!")
        return redirect('profile', username=username)
    
    # Create a new friend request
    friend_request = FriendRequest(from_user=request.user, to_user=to_user)
    friend_request.save()
    messages.success(request, f"Friend request sent to {username}!")
    
    return redirect('profile', username=username)

@login_required(login_url='login')
def accept_friend_request(request, username):
    from_user = get_object_or_404(User, username=username)
    friend_request = get_object_or_404(FriendRequest, from_user=from_user, to_user=request.user)
    
    # Create friendship
    friendship = Friendship(user1=request.user, user2=from_user)
    friendship.save()
    
    # Delete the friend request
    friend_request.delete()
    
    messages.success(request, f"You are now friends with {username}!")
    return redirect('profile', username=username)

@login_required(login_url='login')
def reject_friend_request(request, username):
    from_user = get_object_or_404(User, username=username)
    friend_request = get_object_or_404(FriendRequest, from_user=from_user, to_user=request.user)
    friend_request.delete()
    
    messages.info(request, f"Friend request from {username} rejected.")
    return redirect('profile', username=username)

@login_required(login_url='login')
def friend_list(request):
    # Get all friendships where the current user is either user1 or user2
    friendships = Friendship.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    )
    
    # Extract the friends from the friendships
    friends = []
    for friendship in friendships:
        if friendship.user1 == request.user:
            friends.append(friendship.user2)
        else:
            friends.append(friendship.user1)
    
    friend_requests = FriendRequest.objects.filter(to_user=request.user)
    
    context = {
        'friends': friends,
        'friend_requests': friend_requests,
    }
    
    return render(request, 'friends.html', context)

@login_required(login_url='login')
def unfriend(request, username):
    friend = get_object_or_404(User, username=username)
    
    # Try to find the friendship
    friendship = Friendship.objects.filter(
        Q(user1=request.user, user2=friend) | Q(user1=friend, user2=request.user)
    ).first()
    
    if friendship:
        friendship.delete()
        messages.success(request, f"You are no longer friends with {username}.")
    else:
        messages.error(request, f"You are not friends with {username}.")
    
    return redirect('profile', username=username)

# Messaging Views
@login_required(login_url='login')
def inbox(request):
    # Get distinct users who have sent messages to or received messages from the current user
    message_partners = User.objects.filter(
        Q(sent_messages__receiver=request.user) | Q(received_messages__sender=request.user)
    ).distinct()
    
    context = {
        'message_partners': message_partners,
    }
    
    return render(request, 'inbox.html', context)

@login_required(login_url='login')
def conversation(request, username):
    partner = get_object_or_404(User, username=username)
    
    # Check if users are friends
    is_friend = Friendship.objects.filter(
        Q(user1=request.user, user2=partner) | Q(user1=partner, user2=request.user)
    ).exists()
    
    if not is_friend:
        messages.error(request, "You can only message users who are your friends.")
        return redirect('inbox')
    
    # Get conversation messages
    messages_list = Message.objects.filter(
        Q(sender=request.user, receiver=partner) | Q(sender=partner, receiver=request.user)
    ).order_by('created_at')
    
    # Mark messages as read
    unread_messages = messages_list.filter(receiver=request.user, is_read=False)
    for msg in unread_messages:
        msg.is_read = True
        msg.save()
    
    # Handle regular message sending
    if request.method == 'POST':
        if 'content' in request.POST:
            content = request.POST.get('content')
            if content:
                new_message = Message(sender=request.user, receiver=partner, content=content)
                new_message.save()
                return redirect('conversation', username=username)
        
        # Handle workout invitation
        elif 'workout_invitation' in request.POST:
            workout_id = request.POST.get('workout_id')
            if workout_id:
                workout = get_object_or_404(WorkoutRequest, id=workout_id, user=request.user)
                
                # Create a message with the invitation
                invitation_content = f"📅 Workout Invitation: {workout.body_part} on {workout.date} at {workout.time} ({workout.experience_level} level)"
                new_message = Message(sender=request.user, receiver=partner, content=invitation_content)
                new_message.save()
                
                # Create the workout invitation linked to the message
                invitation = WorkoutInvitation(
                    workout_request=workout,
                    sender=request.user,
                    receiver=partner,
                    message=new_message
                )
                invitation.save()
                
                return redirect('conversation', username=username)
    
    # Get the user's workout requests for the invitation dropdown
    user_workouts = WorkoutRequest.objects.filter(user=request.user, date__gte=timezone.now().date()).order_by('date', 'time')
    print(f"Found {user_workouts.count()} upcoming workouts for user {request.user.username}")
    
    # Let's check if the user has any workout requests at all
    all_user_workouts = WorkoutRequest.objects.filter(user=request.user)
    print(f"User has {all_user_workouts.count()} total workout requests")
    
    # If no upcoming workouts found, include some recent past ones too (just for demonstration)
    if user_workouts.count() == 0:
        # Include recent past workouts too (last 7 days) for demonstration
        user_workouts = WorkoutRequest.objects.filter(
            user=request.user, 
            date__gte=timezone.now().date() - timezone.timedelta(days=7)
        ).order_by('date', 'time')
        print(f"Including recent workouts: now found {user_workouts.count()} workouts")
    
    context = {
        'partner': partner,
        'messages': messages_list,
        'user_workouts': user_workouts,
    }
    
    return render(request, 'conversation.html', context)

@login_required(login_url='login')
@transaction.atomic
@require_http_methods(["POST"])
def respond_workout_invitation(request, invitation_id, action):
    invitation = get_object_or_404(WorkoutInvitation, id=invitation_id, receiver=request.user)
    workout_request = invitation.workout_request
    
    if action == 'accept':
        invitation.status = 'accepted'
        invitation.save()
        
        # Update workout request participant count
        workout_request.current_participants = workout_request.workout_invitations.filter(Q(status='accepted') | Q(status='completed')).count() + 1
        workout_request.is_full = workout_request.current_participants >= workout_request.max_participants
        workout_request.save()
        
        # Send a confirmation message back
        confirmation_message = f"✅ I accepted your invitation to {invitation.workout_request.body_part} on {invitation.workout_request.date} at {invitation.workout_request.time}."
        
        new_message = Message(
            sender=request.user, 
            receiver=invitation.sender, 
            content=confirmation_message
        )
        new_message.save()
        
        messages.success(request, f"You accepted the workout invitation from {invitation.sender.username}.")
    
    elif action == 'decline':
        invitation.status = 'declined'
        invitation.save()
        
        # Update workout request participant count
        workout_request.current_participants = workout_request.workout_invitations.filter(Q(status='accepted') | Q(status='completed')).count() + 1
        workout_request.is_full = workout_request.current_participants >= workout_request.max_participants
        workout_request.save()
        
        # Send a decline message back
        decline_message = f"❌ I can't make it to {invitation.workout_request.body_part} on {invitation.workout_request.date} at {invitation.workout_request.time}."
        
        new_message = Message(
            sender=request.user, 
            receiver=invitation.sender, 
            content=decline_message
        )
        new_message.save()
        
        messages.success(request, f"You declined the workout invitation from {invitation.sender.username}.")
    
    return redirect('inbox')

@login_required
def cancel_workout_invitation(request, invitation_id):
    invitation = get_object_or_404(WorkoutInvitation, id=invitation_id, receiver=request.user)
    invitation.cancel(request.user)
    return JsonResponse({'status': 'success'})

@login_required
def cancel_workout(request, invitation_id):
    invitation = get_object_or_404(WorkoutInvitation, id=invitation_id, receiver=request.user)
    
    # Check if this is the creator's workout request
    if invitation.workout_request.user == request.user:
        # Delete the workout request and all associated invitations
        workout_request = invitation.workout_request
        workout_request.delete()
        
        # Notify all participants
        for invite in WorkoutInvitation.objects.filter(workout_request=workout_request, status='accepted'):
            message = Message(
                sender=request.user,
                receiver=invite.receiver,
                content=f"⚠️ The workout {workout_request.body_part} on {workout_request.date} at {workout_request.time} has been cancelled by the creator."
            )
            message.save()
        
        messages.success(request, "Workout request deleted successfully")
    else:
        # If not the creator, just cancel the invitation
        invitation.cancel(request.user)
        messages.success(request, "Workout cancelled successfully")
    
    return redirect('calendar')

@login_required
def cancel_workout_request(request, workout_id):
    workout_request = get_object_or_404(WorkoutRequest, id=workout_id, user=request.user)
    
    # Get the associated invitations before deleting the workout request
    accepted_invitations = WorkoutInvitation.objects.filter(
        workout_request=workout_request, 
        status='accepted'
    )
    
    # Save information needed for notifications
    body_part = workout_request.body_part
    date = workout_request.date
    time = workout_request.time
    
    # Delete the workout request
    workout_request.delete()
    
    # Notify all participants
    for invite in accepted_invitations:
        message = Message(
            sender=request.user,
            receiver=invite.receiver,
            content=f"⚠️ The workout {body_part} on {date} at {time} has been cancelled by the creator."
        )
        message.save()
    
    messages.success(request, "Workout request deleted successfully")
    return redirect('calendar')

# Calendar API endpoints
def workout_events_api(request):
    """
    API endpoint for FullCalendar to fetch workout events
    Returns JSON in FullCalendar event format
    """
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
        
    # Get accepted workout invitations for the current user
    invitations = WorkoutInvitation.objects.filter(
        receiver=request.user,
        status='accepted'
    ).select_related('workout_request')
    
    # Get workout requests created by the current user
    created_workouts = WorkoutRequest.objects.filter(
        user=request.user,
        is_past=False
    )
    
    events = []
    
    # Add accepted invitations
    for invite in invitations:
        workout = invite.workout_request
        events.append({
            'title': f"{workout.body_part} ({workout.experience_level})",
            'start': f"{workout.date}T{workout.time}",
            'allDay': False,
            'extendedProps': {
                'type': 'invitation',
                'workout_id': workout.id,
                'invitation_id': invite.id,
                'creator': workout.user.username,
                'status': 'accepted'
            }
        })
    
    # Add created workouts
    for workout in created_workouts:
        events.append({
            'title': f"{workout.body_part} ({workout.experience_level})",
            'start': f"{workout.date}T{workout.time}",
            'allDay': False,
            'extendedProps': {
                'type': 'created',
                'workout_id': workout.id,
                'creator': workout.user.username,
                'current_participants': workout.current_participants,
                'max_participants': workout.max_participants
            }
        })
    
    return JsonResponse(events, safe=False)

def upcoming_workouts_api(request):
    """
    API endpoint to get upcoming workouts for the sidebar
    """
    if not request.user.is_authenticated:
        return JsonResponse([], safe=False)
        
    # Get accepted workout invitations for the current user
    invitations = WorkoutInvitation.objects.filter(
        receiver=request.user,
        status='accepted'
    ).select_related('workout_request')
    
    # Get workout requests created by the current user
    created_workouts = WorkoutRequest.objects.filter(
        user=request.user,
        is_past=False
    )
    
    workouts = []
    
    # Add accepted invitations
    for invite in invitations:
        workout = invite.workout_request
        workouts.append({
            'type': 'invitation',
            'title': f"{workout.body_part} ({workout.experience_level})",
            'date': workout.date.strftime('%B %d, %Y'),
            'time': workout.time.strftime('%I:%M %p'),
            'body_part': workout.body_part,
            'experience_level': workout.experience_level,
            'creator': workout.user.username,
            'invitation_id': invite.id,
            'workout_id': workout.id
        })
    
    # Add created workouts
    for workout in created_workouts:
        workouts.append({
            'type': 'created',
            'title': f"{workout.body_part} ({workout.experience_level})",
            'date': workout.date.strftime('%B %d, %Y'),
            'time': workout.time.strftime('%I:%M %p'),
            'body_part': workout.body_part,
            'experience_level': workout.experience_level,
            'current_participants': workout.current_participants,
            'max_participants': workout.max_participants,
            'workout_id': workout.id
        })
    
    # Sort by date and time
    workouts.sort(key=lambda x: (x['date'], x['time']))
    
    return JsonResponse(workouts, safe=False)