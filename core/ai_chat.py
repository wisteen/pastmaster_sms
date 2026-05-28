import json
import os
import google.generativeai as genai
import re

class AIChat:
    def __init__(self):
        self.api_key = os.environ.get('GEMINI_API_KEY', '')
        if not self.api_key:
            raise ValueError('GEMINI_API_KEY is not configured.')
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def markdown_to_html(self, text):
        """Simple markdown to HTML converter"""
        # Bold
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        # Italic
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        # Code blocks
        text = re.sub(r'```(.+?)```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
        # Inline code
        text = re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        # Line breaks
        text = text.replace('\n', '<br>')
        # Lists
        text = re.sub(r'^- (.+)$', r'<li>\1</li>', text, flags=re.MULTILINE)
        text = re.sub(r'(<li>.*</li>)', r'<ul>\1</ul>', text, flags=re.DOTALL)
        return text
    
    def chat(self, user_message, conversation_history=None):
        """Send message to AI and get response"""
        prompt = "You are a helpful school management system assistant. Help users with questions about the LMS, academic management, results, attendance, and general school operations.\n\n use emoji as ur bullet and when communicating"
        
        if conversation_history:
            for msg in conversation_history:
                prompt += f"{msg['role']}: {msg['content']}\n"
        
        prompt += f"user: {user_message}\nassistant:"
        
        try:
            response = self.model.generate_content(prompt)
            # Convert markdown to HTML
            html_response = self.markdown_to_html(response.text.strip())
            return html_response
        except Exception as e:
            return f"Error: {str(e)}"
