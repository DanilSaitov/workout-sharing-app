from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.db.models import Q
from .models import User, WorkoutRequest, FriendRequest, Friendship, Message, WorkoutInvitation
from .forms import WorkoutRequestForm
from django.utils import timezone

# Create your views here.
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email', 'username', 'profile_picture', 'password1', 'password2']

def index(request):
    workout_requests = WorkoutRequest.objects.all().order_by('-created_at')
    
    # Filter parameters
    body_part = request.GET.get('body_part')
    experience_level = request.GET.get('experience_level')
    date = request.GET.get('date')
    search_query = request.GET.get('search')
    
    # Apply filters if provided
    if body_part and body_part != 'All':
        workout_requests = workout_requests.filter(body_part=body_part)
    
    if experience_level and experience_level != 'All':
        workout_requests = workout_requests.filter(experience_level=experience_level)
    
    if date:
        workout_requests = workout_requests.filter(date=date)
    
    # Apply search query if provided
    if search_query:
        workout_requests = workout_requests.filter(
            Q(user__username__icontains=search_query) |
            Q(body_part__icontains=search_query) |
            Q(experience_level__icontains=search_query)
        )
    
    return render(request, 'index.html', {'workout_requests': workout_requests})

def message(request):
    return render(request, 'message.html')

def calendar(request):
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
    return render(request, 'settings.html')

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
def create_workout_request(request):
    form = WorkoutRequestForm()
    if request.method == 'POST':
        form = WorkoutRequestForm(request.POST)
        if form.is_valid():
            workout_request = form.save(commit=False)
            workout_request.user = request.user
            workout_request.save()
            return redirect('index')
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
def respond_workout_invitation(request, invitation_id, action):
    invitation = get_object_or_404(WorkoutInvitation, id=invitation_id, receiver=request.user)
    
    if action == 'accept':
        invitation.status = 'accepted'
        invitation.save()
        
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
        
        # Send a decline message back
        decline_message = f"❌ I can't make it to {invitation.workout_request.body_part} on {invitation.workout_request.date} at {invitation.workout_request.time}."
        
        new_message = Message(
            sender=request.user, 
            receiver=invitation.sender, 
            content=decline_message
        )
        new_message.save()
        
        messages.info(request, f"You declined the workout invitation from {invitation.sender.username}.")
    
    return redirect('conversation', username=invitation.sender.username)