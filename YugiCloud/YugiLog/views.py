from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

def login_user(request):
	if request.method == 'POST':
		username = request.method.POST.get('username')
		password = request.method.POST.get('password')
		user = authenticate(request, username=username, password=password)

		if user is not None:
			login(request, user)
			return redirect("YugiWeb:index")
		else:
			return render(request, 'YugiLog:login', {'error_message': 'Nom d\'utilisateur incorrect'})
		
	else:
		return render(request, 'YugiLog:login', {'error_message': 'Method Error'})

def logout_user(request):
	logout(request)
	return redirect('YugiWeb:index')

def register_user(request):
	if request.method == 'POST':
		username = request.method.POST.get('username')
		password = request.method.POST.get('password')
		
