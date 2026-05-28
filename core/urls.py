from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views, views_features, views_profile, views_attendance_api, views_student_attendance, views_parent_device, views_school_admin, views_ai_chat

app_name = 'core'

urlpatterns = [
    path('role-selection/', views.role_selection_view, name='role_selection'),
    path('login/', views.login_view, name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('school-admin/', views_school_admin.school_admin_dashboard, name='school_admin_dashboard'),
    path('school-admin/users/', views_school_admin.school_admin_users, name='school_admin_users'),
    path('school-admin/students/', views_school_admin.school_admin_students, name='school_admin_students'),
    path('school-admin/transcripts/', views_school_admin.school_admin_transcripts, name='school_admin_transcripts'),
    path('school-admin/staff/', views_school_admin.school_admin_staff, name='school_admin_staff'),
    path('school-admin/academics/', views_school_admin.school_admin_academic_setup, name='school_admin_academic_setup'),
    path('school-admin/assessments/', views_school_admin.school_admin_assessments, name='school_admin_assessments'),
    path('school-admin/class-teachers/', views_school_admin.school_admin_class_teachers, name='school_admin_class_teachers'),
    path('school-admin/head-teachers/', views_school_admin.school_admin_head_teachers, name='school_admin_head_teachers'),
    path('school-admin/parent-wards/', views_school_admin.school_admin_parent_wards, name='school_admin_parent_wards'),
    path('school-admin/grading/', views_school_admin.school_admin_grading, name='school_admin_grading'),
    path('school-admin/exams/', views_school_admin.school_admin_exam_schedules, name='school_admin_exam_schedules'),
    path('school-admin/learner-domains/', views_school_admin.school_admin_learner_domains, name='school_admin_learner_domains'),
    path('school-admin/calendar/events/add/', views_school_admin.school_admin_event_form, name='school_admin_event_add'),
    path('school-admin/calendar/events/<int:event_id>/edit/', views_school_admin.school_admin_event_form, name='school_admin_event_edit'),
    path('school-admin/calendar/holidays/add/', views_school_admin.school_admin_holiday_form, name='school_admin_holiday_add'),
    path('school-admin/calendar/holidays/<int:holiday_id>/edit/', views_school_admin.school_admin_holiday_form, name='school_admin_holiday_edit'),
    path('switch-role/<str:role>/', views.switch_role, name='switch_role'),
    path('switch-school/<slug:slug>/', views.switch_school, name='switch_school'),
    path('activity-log/', views.activity_log, name='activity_log'),
    path('parent/dashboard/', views.parent_dashboard, name='parent_dashboard'),
    path('profile/', views_profile.user_profile, name='user_profile'),
    
    # Feature Control
    path('feature-control/', views_features.feature_control_login, name='feature_control_login'),
    path('feature-control/dashboard/', views_features.feature_control_dashboard, name='feature_control_dashboard'),
    path('feature-control/logout/', views_features.feature_control_logout, name='feature_control_logout'),
    
    # Student URLs
    path('student/results/', views.student_results, name='student_results'),
    path('quiz/<int:quiz_id>/', views.take_quiz, name='take_quiz'),
    
    # Teacher URLs
    path('teacher/results/', views.manage_results, name='manage_results'),
    path('teacher/results-overview/', views.results_overview, name='results_overview'),
    path('teacher/analytics/', views.view_analytics, name='view_analytics'),
    path('teacher/export-results/', views.export_results, name='export_results'),
    path('teacher/component-results/', views.component_results, name='component_results'),
    path('teacher/quiz/', views.quiz_management, name='quiz_management'),
    path('teacher/quiz/create/', views.create_quiz, name='create_quiz'),
    path('teacher/quiz/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('teacher/quiz/<int:quiz_id>/questions/', views.add_questions, name='add_questions'),
    path('teacher/question/<int:question_id>/edit/', views.edit_question, name='edit_question'),
    path('api/delete-question/<int:question_id>/', views.delete_question, name='delete_question'),
    path('teacher/question-bank/', views.question_bank, name='question_bank'),
    path('teacher/subscribe-ai/', views.subscribe_ai, name='subscribe_ai'),
    path('teacher/verify-payment/', views.verify_payment, name='verify_payment'),
    path('teacher/import-questions-ai/', views.import_questions_ai, name='import_questions_ai'),
    path('teacher/create-question-group/', views.create_question_group, name='create_question_group'),
    path('api/add-question-from-bank/', views.add_question_from_bank, name='add_question_from_bank'),
    path('api/add-group-from-bank/', views.add_group_from_bank, name='add_group_from_bank'),
    path('upload-image/', views.upload_image, name='upload_image'),
    path('teacher/quiz/<int:quiz_id>/results/', views.quiz_results, name='quiz_results'),
    path('teacher/quiz/<int:quiz_id>/grade-theory/', views.grade_theory, name='grade_theory'),
    path('api/delete-quiz/<int:quiz_id>/', views.delete_quiz, name='delete_quiz'),
    path('api/students-by-class/', views.get_students_by_class, name='get_students_by_class'),
    path('api/recent-results/', views.get_recent_results, name='get_recent_results'),
    path('api/get-components/', views.get_components, name='get_components'),
    path('api/get-student-results/', views.get_student_results, name='get_student_results'),
    path('api/update-component-score/', views.update_component_score, name='update_component_score'),
    
    # Class Teacher URLs
    path('class-teacher/broadsheet/', views.class_broadsheet, name='class_broadsheet'),
    path('class-teacher/broadsheet/print/', views.print_broadsheet, name='print_broadsheet'),
    path('class-teacher/attendance/', views.manage_attendance, name='manage_attendance'),
    path('class-teacher/promotion/', views.student_promotion, name='student_promotion'),
    path('api/promote-students/', views.promote_students, name='promote_students'),
    path('api/revert-promotion/', views.revert_promotion, name='revert_promotion'),
    path('api/save-broadsheet-comments/', views.save_broadsheet_comments, name='save_broadsheet_comments'),
    path('api/generate-ai-comment/', views.generate_ai_comment, name='generate_ai_comment'),
    
    # Enhanced Quiz
    path('enhanced-quiz/<int:quiz_id>/', views.enhanced_quiz, name='enhanced_quiz'),
    path('view-quiz-result/<int:quiz_id>/', views.view_quiz_result, name='view_quiz_result'),
    
    # Result Checking
    path('check-result/', views.check_result, name='check_result'),
    path('result-card/<str:token>/', views.view_result_card, name='view_result_card'),
    path('view-result/<int:student_id>/<int:term_id>/', views.admin_view_result, name='admin_view_result'),
    path('student-results/', views.student_results_lookup, name='student_results_lookup'),
    path('generate-tokens/', views.generate_tokens, name='generate_tokens'),
    path('report-card-settings/', views.report_card_settings, name='report_card_settings'),
    
    # AI Chat Support
    path('api/ai-chat/', views_ai_chat.ai_chat, name='ai_chat'),
    
    # Mobile Attendance API
    path('api/attendance/mark/', views_attendance_api.mark_attendance, name='api_mark_attendance'),
    path('api/attendance/active-session/', views_attendance_api.get_active_session, name='api_active_session'),
    path('api/attendance/today/<int:session_id>/', views_attendance_api.get_today_attendance, name='api_today_attendance'),
    
    # Parent Device Registration API
    path('api/parent/register-device/', views_parent_device.register_parent_device, name='register_parent_device'),
    path('api/parent/unregister-device/', views_parent_device.unregister_parent_device, name='unregister_parent_device'),
    
    # Student Check-In/Out API
    path('api/student-attendance/', views_student_attendance.student_check_in_out, name='student_check_in_out'),
]
