from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.forms import ModelForm
from .models import User, WorkoutRequest
from .forms import WorkoutRequestForm

# Create your views here.
class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['email', 'username', 'profile_picture', 'password1', 'password2']

def index(request):
    workout_requests = WorkoutRequest.objects.all().order_by('-created_at')
    return render(request, 'index.html', {'workout_requests': workout_requests})

def message(request):
    return render(request, 'message.html')

def browse(request):
    return render(request, 'browse.html')

def calendar(request):
    return render(request, 'calendar.html')

def profile(request, username):
    user = User.objects.get(username=username)
    context = {'user': user}
    return render(request, 'profile.html', context)

@login_required(login_url='login')
def settings(request):
    return render(request, 'settings.html')

def loginPage(request):
    page = 'login'

    if request.user.is_authenticated:
        return redirect('index')

    if request.method == 'POST':
        email = request.POST.get('email').lower()
        password = request.POST.get('password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, 'User does not exist')
            return render(request, 'login_register.html', {'page': page})
        
        user = authenticate(request, email=email, password=password)

        if user is not None:
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, 'Invalid email or password')

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
            login(request, user)
            return redirect('index')
        else:
            messages.error(request, 'An error occurred during registration')

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

def list_workout_requests(request):
    workout_requests = WorkoutRequest.objects.all().order_by('-created_at')
    return render(request, 'index.html', {'workout_requests': workout_requests})