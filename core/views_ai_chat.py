from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
import json
from .ai_chat import AIChat

@login_required
@require_http_methods(["POST"])
def ai_chat(request):
    """Handle AI chat requests"""
    try:
        data = json.loads(request.body)
        user_message = data.get('message', '')
        conversation_history = data.get('history', [])
        
        if not user_message:
            return JsonResponse({'error': 'Message is required'}, status=400)
        
        ai = AIChat()
        response = ai.chat(user_message, conversation_history)
        
        return JsonResponse({
            'response': response,
            'success': True
        })
    except Exception as e:
        return JsonResponse({'error': str(e), 'success': False}, status=500)
