class ActiveRoleMiddleware:
    """
    Applies a granted selected role to request.user for legacy role checks.

    Existing views often inspect request.user.role directly. Keeping the selected
    role on the request user lets those checks work with extra granted roles
    without changing every view at once.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user and user.is_authenticated and not request.path.startswith('/admin/'):
            user.primary_role = getattr(user, 'role', None)
            user.active_school_membership = None
            school = getattr(request, 'school', None)
            selected_role = request.session.get('selected_role')

            if school:
                membership = user.school_memberships.filter(
                    school=school,
                    is_active=True,
                    portal_access_enabled=True,
                ).first()
                user.active_school_membership = membership

                if membership:
                    allowed_roles = membership.get_all_roles()
                    if selected_role not in allowed_roles:
                        selected_role = membership.primary_role
                        request.session['selected_role'] = selected_role
                    user.role = selected_role
                elif not user.is_superuser:
                    request.session.pop('selected_role', None)
                    user.role = 'no_access'
                elif selected_role and user.has_role(selected_role):
                    user.role = selected_role
                else:
                    request.session['selected_role'] = 'super_admin'
                    user.role = 'super_admin'
            elif selected_role and user.has_role(selected_role):
                user.role = selected_role
            elif selected_role:
                request.session.pop('selected_role', None)
                if user.is_superuser:
                    user.role = 'super_admin'

        return self.get_response(request)
