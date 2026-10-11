class School {
  const School({
    required this.name,
    required this.slug,
    required this.baseUrl,
  });

  final String name;
  final String slug;
  final Uri baseUrl;

  Uri get clockInUrl => baseUrl.resolve('/attendance/mark/');

  Uri get loginUrl => baseUrl.resolve('/login/').replace(
        queryParameters: const {
          'role': 'security',
          'next': '/attendance/mark/',
        },
      );

  factory School.fromJson(Map<String, dynamic> json) {
    final name = json['name']?.toString().trim() ?? '';
    final slug = json['slug']?.toString().trim() ?? '';
    final baseUrl = Uri.tryParse(json['base_url']?.toString().trim() ?? '');

    if (name.isEmpty ||
        slug.isEmpty ||
        baseUrl == null ||
        !baseUrl.hasAuthority ||
        (baseUrl.scheme != 'https' && baseUrl.scheme != 'http')) {
      throw const FormatException('Invalid school directory entry.');
    }

    return School(name: name, slug: slug, baseUrl: baseUrl);
  }
}
