import os
import json
import google.generativeai as genai
from django.conf import settings
from .models import QuestionBank, QuestionGroup, Subject

class AIQuestionImporter:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        if not self.api_key:
            raise ValueError('GEMINI_API_KEY is not configured.')
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
    
    def extract_questions_from_text(self, text, subject_id):
        """Extract questions from text using Gemini AI"""
        
        prompt = f"""
You are an expert exam question parser. Analyze the following exam text and extract ALL questions with their details.

IMPORTANT RULES:
1. Identify question packs (groups of questions sharing a common passage/instruction)
2. Detect question types: OBJECTIVE (single correct answer), MULTICHOICE (multiple correct answers), or THEORY (essay/open-ended)
3. For OBJECTIVE: correct_answer should be single letter (e.g., "A")
4. For MULTICHOICE: correct_answer should be comma-separated letters (e.g., "A,B,C")
5. For THEORY: correct_answer should be empty string
6. Keep questions in packs together - DO NOT separate them

Return ONLY valid JSON in this exact format:
{{
  "total_questions": <number>,
  "segments": [
    {{
      "type": "standalone",
      "question": {{
        "question_type": "objective|multichoice|theory",
        "question_text": "...",
        "option_a": "...",
        "option_b": "...",
        "option_c": "...",
        "option_d": "...",
        "correct_answer": "A" or "A,B" or "",
        "difficulty": "easy|medium|hard"
      }}
    }},
    {{
      "type": "pack",
      "instruction": "Common passage or instruction for the group",
      "questions": [
        {{
          "question_type": "objective|multichoice|theory",
          "question_text": "...",
          "option_a": "...",
          "option_b": "...",
          "option_c": "...",
          "option_d": "...",
          "correct_answer": "A",
          "difficulty": "medium"
        }}
      ]
    }}
  ]
}}

EXAM TEXT:
{text}
"""
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text.strip()
            
            # Remove markdown code blocks if present
            if result_text.startswith('```json'):
                result_text = result_text[7:]
            if result_text.startswith('```'):
                result_text = result_text[3:]
            if result_text.endswith('```'):
                result_text = result_text[:-3]
            
            result_text = result_text.strip()
            return json.loads(result_text)
        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")
    
    def import_to_database(self, extracted_data, subject_id, teacher, school_class_id=None):
        """Import extracted questions to database"""
        
        subject = Subject.objects.get(id=subject_id)
        imported_count = 0
        
        for segment in extracted_data.get('segments', []):
            if segment['type'] == 'standalone':
                # Create standalone question
                question_data = segment['question']
                QuestionBank.objects.create(
                    subject=subject,
                    school_class_id=school_class_id,
                    question_type=question_data['question_type'],
                    question_text=question_data['question_text'],
                    option_a=question_data.get('option_a', ''),
                    option_b=question_data.get('option_b', ''),
                    option_c=question_data.get('option_c', ''),
                    option_d=question_data.get('option_d', ''),
                    correct_answer=question_data.get('correct_answer', ''),
                    difficulty=question_data.get('difficulty', 'medium'),
                    created_by=teacher
                )
                imported_count += 1
            
            elif segment['type'] == 'pack':
                # Create question group
                group = QuestionGroup.objects.create(
                    subject=subject,
                    instruction=segment['instruction'],
                    created_by=teacher
                )
                
                # Create questions in the group
                for question_data in segment['questions']:
                    QuestionBank.objects.create(
                        subject=subject,
                        school_class_id=school_class_id,
                        question_type=question_data['question_type'],
                        group=group,
                        question_text=question_data['question_text'],
                        option_a=question_data.get('option_a', ''),
                        option_b=question_data.get('option_b', ''),
                        option_c=question_data.get('option_c', ''),
                        option_d=question_data.get('option_d', ''),
                        correct_answer=question_data.get('correct_answer', ''),
                        difficulty=question_data.get('difficulty', 'medium'),
                        created_by=teacher
                    )
                    imported_count += 1
        
        return imported_count
