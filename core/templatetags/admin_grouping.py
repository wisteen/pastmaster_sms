from django import template

register = template.Library()


GROUPS = [
    {
        "name": "Quick Links",
        "icon": "fas fa-bolt",
        "models": {
            "dashboard",
            "generate tokens",
        },
    },
    {
        "name": "Users and People",
        "icon": "fas fa-users-cog",
        "models": {
            "auth.group",
            "core.user",
            "core.student",
            "core.teacher",
            "core.classteacher",
            "core.headteacher",
            "core.schoolmembership",
            "core.studentbiodata",
            "core.guardian",
            "core.staffbiodata",
            "core.staffqualification",
            "core.staffguarantor",
            "core.staffbankaccount",
        },
    },
    {
        "name": "School Setup",
        "icon": "fas fa-school",
        "models": {
            "core.schooltenant",
            "core.schooldomain",
            "core.tenantfeatureoverride",
            "core.schoolclass",
            "core.subject",
            "core.term",
            "core.schoolsettings",
            "core.reportcardsettings",
        },
    },
    {
        "name": "Academic Planning",
        "icon": "fas fa-book-open",
        "models": {
            "core.curriculum",
            "core.learningobjective",
            "core.syllabuscontent",
            "core.lessonplan",
            "core.lessonnote",
            "core.curriculumcoverage",
            "core.academicevent",
            "core.holiday",
            "core.assignment",
            "core.assignmentsubmission",
            "core.submissionfile",
        },
    },
    {
        "name": "Timetable and Facilities",
        "icon": "fas fa-calendar-alt",
        "models": {
            "core.timeslot",
            "core.roomassignment",
            "core.timetable",
        },
    },
    {
        "name": "Results and Assessment",
        "icon": "fas fa-chart-bar",
        "models": {
            "core.gradingsystem",
            "core.resultcomponent",
            "core.componentresult",
            "core.result",
            "core.resulttoken",
            "core.comment",
            "core.psychomotor",
            "core.effectivedomain",
            "core.examschedule",
        },
    },
    {
        "name": "Quiz and Questions",
        "icon": "fas fa-question-circle",
        "models": {
            "core.questionbank",
            "core.questiongroup",
            "core.questiongroupinstance",
            "core.quiz",
            "core.question",
            "core.quizattempt",
            "core.quizanswer",
            "core.aisubscription",
        },
    },
    {
        "name": "Attendance and Security",
        "icon": "fas fa-user-check",
        "models": {
            "core.attendance",
            "core.attendancerecord",
            "core.visitor",
        },
    },
    {
        "name": "Finance Management",
        "icon": "fas fa-money-bill-wave",
        "models": {
            "core.feestructure",
            "core.studentfee",
            "core.feepayment",
            "core.financialtransaction",
            "core.scholarship",
            "core.scholarshiprecipient",
            "core.payrollstructure",
            "core.staffpayroll",
            "core.teacherloan",
            "core.payrolldeduction",
            "core.financialauditlog",
        },
    },
    {
        "name": "Library Management",
        "icon": "fas fa-book",
        "models": {
            "core.bookcategory",
            "core.book",
            "core.bookborrowing",
            "core.digitalresource",
        },
    },
    {
        "name": "Website Management",
        "icon": "fas fa-globe",
        "models": {
            "website.websiteprofile",
            "website.websitepage",
            "website.websitesection",
            "website.websitecontentitem",
            "website.websiteteammember",
            "website.newspost",
            "website.galleryimage",
            "website.newslettersubscriber",
            "website.newsletterissue",
            "website.faq",
            "website.downloadableform",
            "website.inquiry",
        },
    },
    {
        "name": "System, Reports and Notifications",
        "icon": "fas fa-cogs",
        "models": {
            "core.featureflag",
            "core.featurecontroladmin",
            "core.systemlicense",
            "core.tenantdataexportrequest",
            "core.notificationtemplate",
            "core.notificationlog",
            "core.generatedreport",
        },
    },
]


@register.filter
def group_admin_menu(apps):
    grouped = [
        {
            "name": group["name"],
            "icon": group["icon"],
            "items": [],
        }
        for group in GROUPS
    ]
    fallback = {"name": "Other Admin Tools", "icon": "fas fa-ellipsis-h", "items": []}
    index = {
        model_name: grouped[group_index]
        for group_index, group in enumerate(GROUPS)
        for model_name in group["models"]
    }

    for app in apps or []:
        for item in app.get("models", []):
            model_key = item.get("model_str")
            if not model_key:
                model_key = item.get("name", "").lower()

            bucket = index.get(model_key, fallback)
            bucket["items"].append(item)

    result = [group for group in grouped if group["items"]]
    if fallback["items"]:
        result.append(fallback)
    return result
