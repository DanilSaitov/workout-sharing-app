from django.shortcuts import render

# Create your views here.
def index(request):
    return render(request, 'index.html')

def message(request):
    return render(request, 'message.html')

def browse(request):
    return render(request, 'browse.html')

def calendar(request):
    return render(request, 'calendar.html')

def settings(request):
    return render(request, 'settings.html')
