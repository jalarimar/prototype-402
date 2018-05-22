from django.shortcuts import render, redirect
from django.views import generic
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import login, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required

import requests
import time

from .forms import SignUpForm
from .models import User, Question, SkillArea, TestCase, Token


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('/')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password successfully updated')
            return redirect('/')
        else:
            messages.error(request, 'Please correct the error')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'registration/change_password.html', {'form': form })


class ProfileView(generic.DetailView):
    """displays user's profile"""
    template_name = 'registration/profile.html'
    model = User

    def get_object(self):
        return User.objects.get(username=self.request.user.username)


class IndexView(generic.ListView):
    """displays list of skills"""
    template_name = 'questions/index.html'
    context_object_name = 'skill_list'

    def get_queryset(self):
        return SkillArea.objects.order_by('name')


class SkillView(generic.DetailView):
    """displays list of questions which involve this skill"""
    template_name = 'questions/skill.html'
    context_object_name = 'skill'
    model = SkillArea


class QuestionView(generic.DetailView):
    """displays question page"""
    template_name = 'questions/question.html'
    model = Question

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context[''] = ''
        return context



BASE_URL = "http://36adab90.compilers.sphere-engine.com/api/v3/submissions/"
TOKEN = "?access_token=" + Token.objects.get(pk='sphere').token
PYTHON = 116
COMPLETED = 0
PROGRAM = 1
FUNCTION = 2

COMMON_ABOVE = """
import json

real_print = print
T = 0
n = 0

"""

COMMON_MID = """
N_test_cases = len(test_returns)
correct = [False] * N_test_cases
printed = [''] * N_test_cases
returned = [None] * N_test_cases

def next_question():
    global T, n
    T += 1
    n = 0

def input(prompt=""):
    global n
    if n >= len(test_inputs[T]):
        raise EOFError()
    if len(prompt) > 1:
        print(prompt)
    test_input = test_inputs[T][n]
    n += 1
    return test_input

def print(user_output):
    if T < N_test_cases:
        user_output += '\\\\n'
        printed[T] += user_output

"""

COMMON_BELOW = """
for index in hidden:
    test_params[index] = ["hidden"]
    test_inputs[index] = ["hidden"]
    test_outputs[index] = "hidden"
    test_returns[index] = "hidden"
    printed[index] = "hidden"
    returned[index] = "hidden"

results = {
    'correct': correct,
    'printed': printed,
    'returned': returned,
    'inputs': test_inputs,
    'params': test_params,
    'expected_prints': test_outputs,
    'expected_returns': test_returns,
}
real_print(json.dumps(results))

"""


def format_test_data(test_cases):
    test_params = "\ntest_params = ["
    test_inputs = "\ntest_inputs = ["
    test_outputs = "\ntest_outputs = ["
    test_returns = "\ntest_returns = ["
    hidden = "\nhidden = []" #todo

    for case in test_cases:
        param_str = repr(case.function_params.split(',')) + ","
        input_str = repr(case.test_input.split('\n')) + ","
        output_str = repr(case.expected_output) + ","
        return_str = repr(case.expected_return) + ","

        test_params += param_str
        test_inputs += input_str
        test_outputs += output_str
        test_returns += return_str

    test_params = test_params[:-1] + "]\n"
    test_inputs = test_inputs[:-1] + "]\n"
    test_outputs = test_outputs[:-1] + "]\n"
    test_returns = test_returns[:-1] + "]\n"

    test_data = test_params + test_inputs + test_outputs + test_returns + hidden

    return test_data

def add_program_test_code(question, user_code):
    test_cases = question.test_cases.all()
    
    test_data = format_test_data(test_cases)

    repeated_user_code = ''
    for case in test_cases:
        repeated_user_code += user_code
        repeated_user_code += '\nnext_question()\n'

    processing = repeated_user_code + \
        '\nfor i in range(N_test_cases):\n' + \
        '    expected_output = test_outputs[i]\n' + \
        '    if printed[i] != expected_output:\n' + \
        '        correct[i] = False\n' + \
        '    else:\n' + \
        '        correct[i] = True\n'

    complete_code = COMMON_ABOVE + test_data + COMMON_MID + processing + COMMON_BELOW
    return complete_code


def add_function_test_code(question, user_code):
    test_cases = question.test_cases.all()

    test_data = format_test_data(test_cases)

    processing = user_code + \
        '\nfor i in range(N_test_cases):\n' + \
        '    params = test_params[i]\n' + \
        '    result = ' + question.function_name + '(*params)\n' + \
        '    returned[i] = result\n' + \
        '    if result == test_returns[i]:\n' + \
        '        correct[i] = True\n' + \
        '    next_question()\n' + \
        '    expected_output = test_outputs[i]\n' + \
        '    if printed[i] != expected_output:\n' + \
        '        correct[i] = False\n'

    complete_code = COMMON_ABOVE + test_data + COMMON_MID + processing + COMMON_BELOW
    return complete_code


def send_code(request):
    code = request.POST.get('user_input')
    question_id = request.POST.get('question')
    question = Question.objects.get(pk=question_id)

    if question.question_type == PROGRAM:
        code = add_program_test_code(question, code)
    elif question.question_type == FUNCTION:
        code = add_function_test_code(question, code)
    
    response = requests.post(BASE_URL + TOKEN, data = {"language": PYTHON, "sourceCode": code})
    result = response.json()

    return JsonResponse(result)

def get_output(request):
    submission_id = request.GET.get('id')
    question_id = request.GET.get('question')

    params = {
        "withOutput": True, 
        "withStderr": True, 
        "withCmpinfo": True
    }
    response = requests.get(BASE_URL + submission_id + TOKEN, params=params)
    result = response.json()

    if result["status"] == COMPLETED:
        result["completed"] = True
    else:
        result["completed"] = False

    return JsonResponse(result)
    